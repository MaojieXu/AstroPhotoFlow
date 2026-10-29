from threading import Event

from astrophotoflow.modules.data.preview_executor import PreviewExecutor


def test_foreground_and_visible_previews_run_before_queued_background_work():
    entered, release = Event(), Event()
    order = []
    def block():
        entered.set()
        assert release.wait(5)
    with PreviewExecutor(1) as executor:
        running = executor.submit(block)
        try:
            assert entered.wait(5)
            background = executor.submit_background("other", order.append, "background")
            visible = executor.submit_background("visible", order.append, "visible")
            foreground = executor.submit(order.append, "foreground")
            executor.prioritize({"visible"})
        finally:
            release.set()
        for future in (running, background, visible, foreground):
            future.result(5)
    assert order == ["foreground", "visible", "background"]
    assert executor._shutdown


def test_preview_shutdown_drains_work_and_propagates_job_failures():
    def fail():
        raise ValueError("preview failed")
    executor = PreviewExecutor(1)
    failure = executor.submit(fail)
    success = executor.submit(lambda: "finished")
    executor.shutdown()
    assert isinstance(failure.exception(), ValueError)
    assert success.result() == "finished"
