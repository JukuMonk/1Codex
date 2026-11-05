"""Bounded adapter for the FileStorage ZIP observed in 1C 8.5.1.1529 HBK.

The layout is taken from the UP FM02 probes, not inferred from archive names.
Extraction is explicit, selected and cached by archive SHA/platform/patterns.
It never executes help content or uses ZipFile.extractall().
"""
from pathlib import Path, PurePosixPath
import argparse
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import struct
import tempfile
import time
import uuid
import zipfile
import zlib

PROFILE = '8.5.1.1529'
SENTINEL = 0x7fffffff
HEADER = re.compile(rb'\r\n([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) \r\n')
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_BLOCK = 256 * 1024 * 1024


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


class Container:
    """Only the measured uncompressed FileStorage container/ZIP variant."""
    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        if not 47 <= self.size <= MAX_ARCHIVE: raise ValueError('HBK archive size is outside the supported bounds')
        self.file = self.path.open('rb')
        signature = self.file.read(16)
        if len(signature) != 16 or struct.unpack_from('<I',signature)[0] != SENTINEL:
            self.close(); raise ValueError('Unknown HBK container signature')

    def close(self): self.file.close()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

    def block(self, offset, max_bytes=MAX_BLOCK):
        result = bytearray(); total = None; visited = set()
        while offset != SENTINEL:
            if offset in visited or len(visited) >= 10000: raise ValueError('Cyclic or excessive HBK page chain')
            visited.add(offset)
            if offset < 16 or offset + 31 > self.size: raise ValueError('HBK block offset outside archive')
            self.file.seek(offset); header = self.file.read(31)
            match = HEADER.fullmatch(header)
            if not match: raise ValueError('Invalid HBK block header')
            declared, page, following = (int(value,16) for value in match.groups())
            if total is None:
                total = declared
                if total > max_bytes: raise ValueError('HBK block exceeds bounded size')
            if not page and len(result) < total: raise ValueError('Empty HBK continuation page')
            take = min(total-len(result),page)
            if offset + 31 + take > self.size: raise ValueError('Truncated HBK block data')
            part = self.file.read(take)
            if len(part) != take: raise ValueError('Truncated HBK block data')
            result.extend(part)
            if len(result) >= total: return bytes(result)
            offset = following
        if total is None or len(result) != total: raise ValueError('Incomplete HBK page chain')
        return bytes(result)

    def storage_zip(self):
        index = self.block(16, max_bytes=120000)
        if len(index) % 12: raise ValueError('HBK directory index is not a 12-byte tuple sequence')
        bodies = []
        for index_offset in range(0,len(index),12):
            head,body,_ = struct.unpack_from('<III',index,index_offset)
            header = self.block(head,max_bytes=4096)
            if len(header) < 20 or (len(header)-20) % 2: raise ValueError('Invalid HBK directory entry name')
            try: name = header[20:].decode('utf-16le').rstrip('\0')
            except UnicodeDecodeError as error: raise ValueError('Invalid HBK entry encoding') from error
            if name == 'FileStorage': bodies.append(body)
        if len(bodies) != 1: raise ValueError('Expected exactly one verified FileStorage ZIP')
        return self.block(bodies[0])


def safe_member(name):
    if not name or '\\' in name or '\0' in name or ':' in name:
        raise ValueError('Unsafe HBK ZIP member')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('HBK ZIP member escapes extraction root')
    return path


def check_cache(manifest_path, identity, cache_root):
    try: data = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError) as error: raise ValueError('Damaged HBK cache manifest; rebuild explicitly') from error
    if data.get('schema_version') != 1 or data.get('identity') != identity:
        raise ValueError('HBK cache identity mismatch')
    location = data.get('location','')
    safe_member(location)
    source = (cache_root/location).resolve()
    if not source.is_relative_to(cache_root): raise ValueError('HBK cache path escapes root')
    for relative,digest in data.get('files',{}).items():
        safe_member(relative)
        path = (source/relative).resolve()
        if not path.is_relative_to(source) or not path.is_file() or file_sha(path) != digest:
            raise ValueError('Damaged extracted HBK source; rebuild explicitly')
    if not data.get('files'): raise ValueError('Empty HBK source cache')
    return source,data


def extract_hbk(archive_path, cache_root, platform_version, includes, *, max_files=2000,
                max_file_bytes=2_000_000, max_total_bytes=128*1024*1024,
                progress=None, rebuild=False):
    started = time.monotonic()
    if platform_version != PROFILE: raise ValueError('HBK layout is verified only for platform '+PROFILE)
    if not includes or len(includes) > 32 or any(not isinstance(p,str) or not p for p in includes):
        raise ValueError('Specify 1..32 bounded inclusion patterns')
    if not 1 <= max_files <= 200000 or not 1 <= max_file_bytes <= 16*1024*1024 or not 1 <= max_total_bytes <= 512*1024*1024:
        raise ValueError('Extraction bounds are invalid')
    archive,cache = Path(archive_path).resolve(),Path(cache_root).resolve()
    if not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE:
        raise ValueError('Missing or oversized HBK archive')
    archive_sha = file_sha(archive)
    identity = {'archive_sha256':archive_sha,'platform_version':platform_version,
                'includes':sorted(set(includes)), 'max_files':max_files,
                'max_file_bytes':max_file_bytes,'max_total_bytes':max_total_bytes}
    key = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    manifest = cache/'manifests'/(key+'.json')
    if manifest.is_file() and not rebuild:
        source,data = check_cache(manifest,identity,cache)
        return {'source_root':str(source),'manifest':str(manifest),'cache_hit':True,
                'files':len(data['files']),'archive_sha256':archive_sha,'seconds':time.monotonic()-started,
                'profile':PROFILE,'archive_parsed':False}
    cache.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.hbk-stage-',dir=cache))
    try:
        with Container(archive) as container:
            storage = container.storage_zip()
        try:
            with zipfile.ZipFile(io.BytesIO(storage)) as package:
                infos = package.infolist()
                if len(infos) > 200000: raise ValueError('HBK ZIP entry count exceeds limit')
                selected,seen,total = [],set(),0
                for info in infos:
                    safe_member(info.orig_filename)
                    relative = safe_member(info.filename)
                    if (info.external_attr >> 16) & 0xf000 == 0xa000:
                        raise ValueError('HBK ZIP symlinks are unsupported')
                    if info.is_dir(): continue
                    if relative.suffix.casefold() not in {'.html','.htm'}: continue
                    if not any(fnmatch.fnmatchcase(info.filename,pattern) for pattern in identity['includes']):continue
                    if info.filename.casefold() in seen: raise ValueError('Duplicate HBK extraction path')
                    seen.add(info.filename.casefold())
                    if info.file_size > max_file_bytes: raise ValueError('Selected HBK page exceeds limit')
                    total += info.file_size; selected.append(info)
                if not selected: raise ValueError('No HTML pages match requested HBK paths')
                if len(selected) > max_files or total > max_total_bytes: raise ValueError('Selected HBK pages exceed extraction bounds')
                hashes = {}; written = 0
                for position,info in enumerate(selected,1):
                    path = (stage/info.filename).resolve()
                    if not path.is_relative_to(stage.resolve()): raise ValueError('HBK target escapes staging directory')
                    path.parent.mkdir(parents=True,exist_ok=True)
                    with package.open(info) as member:
                        raw = member.read(max_file_bytes+1)
                    if len(raw) != info.file_size or len(raw) > max_file_bytes: raise ValueError('HBK decompressed page size mismatch')
                    path.write_bytes(raw)
                    hashes[info.filename] = hashlib.sha256(raw).hexdigest()
                    written += len(raw)
                    if progress and (position % 100 == 0 or position == len(selected)):
                        progress({'processed':position,'total':len(selected),'bytes':written})
        except (zipfile.BadZipFile,NotImplementedError,zlib.error) as error:
            raise ValueError('Unsupported or corrupt HBK FileStorage ZIP') from error
        if file_sha(archive) != archive_sha: raise ValueError('HBK archive changed during extraction')
        destination = cache/'data'/(key[:24]+'-'+uuid.uuid4().hex[:8])
        destination.parent.mkdir(parents=True,exist_ok=True)
        os.replace(stage,destination)
        data = {'schema_version':1,'identity':identity,'location':destination.relative_to(cache).as_posix(),'files':hashes}
        manifest.parent.mkdir(parents=True,exist_ok=True)
        pending = manifest.with_name(manifest.name+'.'+uuid.uuid4().hex+'.pending')
        try:
            pending.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(pending,manifest)
        finally:
            if pending.exists(): pending.unlink()
        return {'source_root':str(destination),'manifest':str(manifest),'cache_hit':False,
                'files':len(hashes),'archive_sha256':archive_sha,'seconds':time.monotonic()-started,
                'profile':PROFILE,'archive_parsed':True}
    finally:
        if stage.exists():
            resolved = stage.resolve()
            if not resolved.is_relative_to(cache) or not resolved.name.startswith('.hbk-stage-'):
                raise ValueError('Unsafe HBK staging cleanup')
            shutil.rmtree(resolved)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path);parser.add_argument('cache',type=Path)
    parser.add_argument('--platform',required=True)
    parser.add_argument('--include',action='append',required=True)
    parser.add_argument('--max-files',type=int,default=2000)
    parser.add_argument('--rebuild',action='store_true')
    args=parser.parse_args()
    result=extract_hbk(args.archive,args.cache,args.platform,args.include,max_files=args.max_files,
                       rebuild=args.rebuild,progress=lambda value: print(json.dumps({'progress':value}),flush=True))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
