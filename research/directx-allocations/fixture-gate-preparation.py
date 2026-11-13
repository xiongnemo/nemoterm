from pathlib import Path
root=Path(__file__).resolve().parents[2]
stage=root/'build/local-directx-allocation-probe'
path=stage/'tests/tabs_window_smoke.py'
text=path.read_text(encoding='utf-8')
anchor="                evidence['workload']=memory_exercise(memory_sampler,first,second,output,select,resources,host,scene)"
replacement="""                from working_set_regions import private_regions
                evidence['allocation_probe_instrumented']=True
                probe_dir=root/'research'
                write_snapshot(probe_dir/'allocation-ready.json',dict(pid=process.pid,
                    executable=str(exe),epoch_ms=round(time.time()*1000),
                    before_regions=private_regions(handle)))
                wait_for(lambda:read_snapshot(probe_dir/'allocation-release.json'),timeout=90)
                evidence['workload']=memory_exercise(memory_sampler,first,second,output,select,resources,host,scene)
                write_snapshot(probe_dir/'allocation-done.json',dict(pid=process.pid,
                    epoch_ms=round(time.time()*1000),after_regions=private_regions(handle)))
                wait_for(lambda:read_snapshot(probe_dir/'allocation-detached.json'),timeout=70)"""
assert text.count(anchor)==1
text=text.replace(anchor,replacement)
text=text.replace("memory=memory_sampler.stop();memory_sampler=None",
                  "memory=memory_sampler.stop();memory_sampler=None;memory['injected']=True")
path.write_text(text,encoding='utf-8')
