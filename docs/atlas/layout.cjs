// Dagre is only a build dependency. The delivered HTML contains static SVG.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const sandbox = {structuredClone};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'vendor/dagre-3.1.3.min.js'),'utf8'),sandbox);
const data=JSON.parse(fs.readFileSync(0,'utf8'));
for(const map of data){
  const g=new sandbox.dagre.graphlib.Graph({multigraph:true}).setGraph({rankdir:'TB',nodesep:24,ranksep:54,marginx:32,marginy:28,ranker:'network-simplex'}).setDefaultEdgeLabel(()=>({}));
  for(const n of map.nodes) g.setNode(n.id,{width:224,height:116});
  map.edges.forEach((e,i)=>g.setEdge(e.a,e.b,{width:e.label ? Math.max(68,e.label.length*6.8):0,height:e.label?18:0,weight:e.kind==='back'?0.1:1},String(i)));
  sandbox.dagre.layout(g);
  map.layout={width:g.graph().width,height:g.graph().height};
  for(const n of map.nodes) Object.assign(n,g.node(n.id));
  map.edges.forEach((e,i)=>Object.assign(e,g.edge({v:e.a,w:e.b,name:String(i)})));
}
process.stdout.write(JSON.stringify(data));
