from __future__ import annotations
import asyncio, logging
from datetime import datetime, timezone

log = logging.getLogger("tier1")


def _field(token: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in token.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part in ("*", ""):
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = int(part)
            b = hi if step != 1 else a
        if a < lo or b > hi or a > b or step < 1:
            raise ValueError(f"cron field out of range: {token}")
        out.update(range(a, b + 1, step))
    return out


def parse_cron(spec: str):
    f = spec.split()
    if len(f) != 5:
        raise ValueError("cron needs 5 fields: minute hour day month weekday")
    dow = {0 if d == 7 else d for d in _field(f[4], 0, 7)}
    return _field(f[0], 0, 59), _field(f[1], 0, 23), _field(f[2], 1, 31), _field(f[3], 1, 12), dow, \
        f[2] != "*", f[4] != "*"


def cron_matches(spec: str, dt: datetime) -> bool:
    mi, h, dom, mo, dow, dom_r, dow_r = parse_cron(spec)
    if dt.minute not in mi or dt.hour not in h or dt.month not in mo:
        return False
    d_ok, w_ok = dt.day in dom, ((dt.weekday() + 1) % 7) in dow
    return (d_ok or w_ok) if (dom_r and dow_r) else (d_ok and w_ok)


class Scheduler:
    def __init__(self, store, orch, runner=None, notifier=None, kb=None):
        self.store, self.orch, self._task = store, orch, None
        self.runner, self.notifier, self.kb = runner, notifier, kb

    async def fire(self, name: str, extra: str = "") -> dict:
        job = self.store.job_get(name)
        if not job:
            raise KeyError(name)
        prompt = job["prompt"].replace("{input}", extra) if extra else job["prompt"].replace("{input}", "")
        try:
            trig = f"{job['kind']}:{name}"
            res = await (self.runner(prompt, trigger=trig) if self.runner else self.orch.run(prompt, trigger=trig))
            self.store.job_mark(name, last_run=res["run_id"], last_status=res["status"])
            if self.notifier:
                await self.notifier.send("job_done", f"Job {name}: {res['status']}\n{res['answer'][:1500]}",
                                         {"job": name, "run_id": res["run_id"], "status": res["status"]})
            return res
        except Exception as e:
            self.store.job_mark(name, last_status=f"failed: {type(e).__name__}")
            if self.notifier:
                await self.notifier.send("job_failed", f"Job {name} failed: {type(e).__name__}", {"job": name})
            raise

    async def tick(self, now: datetime | None = None) -> list[str]:
        now = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
        minute, fired = now.isoformat(), []
        for j in self.store.jobs_list():
            if j["kind"] != "cron" or not j["enabled"] or j["last_minute"] == minute:
                continue
            try:
                if cron_matches(j["spec"], now):
                    self.store.job_mark(j["name"], last_minute=minute)
                    fired.append(j["name"])
                    asyncio.create_task(self._safe(j["name"]))
            except ValueError:
                log.warning("invalid cron spec on job %s", j["name"])
        return fired

    async def _safe(self, name):
        try:
            await self.fire(name)
        except Exception as e:
            log.warning("job %s failed: %s", name, e)

    async def loop(self):
        while True:
            await self.tick()
            if self.kb is not None:
                try:
                    await asyncio.to_thread(self.kb.sync_vault)
                except Exception as e:
                    log.warning("vault sync failed: %s", e)
            await asyncio.sleep(15)

    def start(self):
        self._task = asyncio.create_task(self.loop())

    def stop(self):
        if self._task:
            self._task.cancel()
