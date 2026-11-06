"""Progress watchdog. Only explicit checkpoints count; CPU usage never does."""
from dataclasses import dataclass
import subprocess
import time


class StalledOperation(RuntimeError):
    def __init__(self, event):
        self.event = event
        super().__init__(event['kind'])


@dataclass(frozen=True)
class Phase:
    name: str
    expected_seconds: float | None = None
    cancel_safe: bool = False
    warn_seconds: float = 60
    stop_seconds: float = 120

    def __post_init__(self):
        if not self.name or self.warn_seconds <= 0 or self.stop_seconds <= self.warn_seconds:
            raise ValueError('Expected 0 < warning < stop threshold and a phase name')
        if self.expected_seconds is not None and self.expected_seconds <= 0:
            raise ValueError('Expected duration must be positive')


class Watchdog:
    def __init__(self, phase, *, clock=time.monotonic):
        self.phase = phase
        self.clock = clock
        self.started = self.last_progress = clock()
        self.token = None
        self.warned = False
        self.slow_warned = False
        self.stopped = False

    def progress(self, token):
        """Caller derives token from completed work, e.g. processed file count.

        Poll count, CPU, unchanged file length or elapsed time are not progress.
        None means no observable progress and does not reset the deadline.
        """
        if token is not None and token != self.token:
            self.token = token
            self.last_progress = self.clock()
            self.warned = False

    def event(self, kind):
        now = self.clock()
        return {'kind': kind, 'phase': self.phase.name,
                'elapsed_seconds': round(now-self.started, 3),
                'without_progress_seconds': round(now-self.last_progress, 3),
                'cancel_safe': self.phase.cancel_safe}

    def access_denied(self):
        return self.event('access_denied')

    def check(self):
        now = self.clock()
        if now < self.last_progress: raise ValueError('Monotonic clock moved backwards')
        if now-self.last_progress >= self.phase.stop_seconds and not self.stopped:
            self.stopped = True
            return self.event('stalled_cancel_safe' if self.phase.cancel_safe else 'stalled_unsafe')
        if now-self.last_progress >= self.phase.warn_seconds and not self.warned:
            self.warned = True
            return self.event('no_progress_warning')
        if (self.phase.expected_seconds is not None and now-self.started >= 2*self.phase.expected_seconds
                and not self.slow_warned):
            self.slow_warned = True
            return self.event('duration_warning')
        return None


class RetryGate:
    """An unchanged failure context cannot be retried by this helper."""
    def __init__(self): self.failures = {}

    def failed(self, error_code, conditions_fingerprint):
        if not error_code or not conditions_fingerprint: raise ValueError('Failure context required')
        self.failures[error_code] = conditions_fingerprint

    def check(self, error_code, conditions_fingerprint):
        if not conditions_fingerprint: raise ValueError('Current conditions are required')
        if self.failures.get(error_code) == conditions_fingerprint:
            raise ValueError('Retry requires a concrete change of conditions')
        return True


def journal_reporter(journal, stage_id):
    """Send watchdog events to a timing stage without exposing process details."""
    try:
        from . import timing
    except ImportError:
        import timing
    kinds = {
        'duration_warning': ('warning', 'Превышена ожидаемая длительность'),
        'no_progress_warning': ('warning', 'Watchdog не видит прогресса'),
        'access_denied': ('stalled', 'Watchdog обнаружил отказ в доступе'),
        'stalled_cancel_safe': ('stalled', 'Истёк срок ожидания безопасно прерываемой операции'),
        'stalled_unsafe': ('stalled', 'Истёк срок ожидания операции, требуется диагностика'),
    }
    def report(event):
        kind, message = kinds[event['kind']]
        timing.signal(journal, stage_id, kind, message)
    return report


def run_monitored(process, progress_provider, phase, *, on_event=lambda event: None,
                  access_denied_provider=lambda: False, clock=time.monotonic,
                  sleep=time.sleep, poll_seconds=0.25, termination_grace=5):
    """Wait for an already launched own Popen; never accepts an arbitrary PID.

    Safe cancellation invokes only the given child's terminate, then waits a
    bounded grace period. It never escalates to killing a process tree. Unsafe
    writes remain running; StalledOperation tells the adapter to inspect safe
    completion and retain the process handle instead of waiting silently.
    No command, connection string, PID inventory or exception text is logged.
    """
    if not isinstance(process, subprocess.Popen):
        raise TypeError('An owned subprocess.Popen handle is required')
    if not 0 < poll_seconds <= 5 or termination_grace < 0: raise ValueError('Invalid polling/grace')
    monitor = Watchdog(phase, clock=clock)
    while process.poll() is None:
        monitor.progress(progress_provider())
        if access_denied_provider():
            event = monitor.access_denied(); on_event(event)
            if phase.cancel_safe: process.terminate()
            raise StalledOperation(event)
        event = monitor.check()
        if event:
            on_event(event)
            if event['kind'].startswith('stalled_'):
                if phase.cancel_safe:
                    process.terminate()
                    try: process.wait(timeout=termination_grace)
                    except subprocess.TimeoutExpired: pass
                raise StalledOperation(event)
        sleep(poll_seconds)
    return process.returncode
