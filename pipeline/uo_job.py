# Runs a long script (render_uo_layer.py, uo_cloth_bake.py) step by step, so that Blender's window stays alive.
#
# A script that loops for minutes inside "Run Script" never gives control back to Blender: the window is not redrawn, the system
# marks it "Not Responding" (Blender 5.x on Windows shows this much sooner than 4.2) and it looks like a crash. Here the script
# is a generator that yields after every unit of work (a frame, a cloth step); run() feeds it from a modal operator:
#   * between two steps Blender redraws; the progress is in the status bar (bottom of the window) and on the mouse cursor;
#   * ESC cancels (the script's own clean-up runs, like with a STOP file); the other input is blocked while it works;
#   * in background mode (blender -b, the bpy module, the tests) the generator simply runs to the end, exceptions included.
# Usage:  uo_job = bpy.data.texts["uo_job.py"].as_module();  uo_job.run(generator, "title", finish, abort)
#   generator : yields a short progress text (or None) after each step; raising / being closed ends it
#   finish()  : called once after the last step          abort(why) : called after ESC, an error or STOP (generator already closed)
import time
import traceback

import bpy

BUDGET = 0.1            # s: steps run back to back until this much time passed since the last redraw (one step is at least run)


def _end(gen, why, finish, abort):
    if why is None:
        if finish:
            finish()
        return
    try:
        gen.close()                                   # runs the finally: blocks of the generator
    finally:
        if abort:
            abort(why)


class UO_OT_job(bpy.types.Operator):
    bl_idname = "wm.uo_job"
    bl_label = "UO job"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        wm = context.window_manager
        self._t = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        self._n = 0
        wm.progress_begin(0, 1000)
        self._text(context, "starting (ESC cancels)")
        return {"RUNNING_MODAL"}

    def _text(self, context, msg):
        title = _job()["title"]
        if context.workspace is not None:
            context.workspace.status_text_set("%s: %s   [ESC = cancel]" % (title, msg))
        if context.window_manager is not None:
            context.window_manager.progress_update(self._n % 1000)

    def _done(self, context, why):
        wm = context.window_manager
        wm.event_timer_remove(self._t)
        wm.progress_end()
        if context.workspace is not None:
            context.workspace.status_text_set(None)
        job = dict(_job()); _job().clear()
        try:
            _end(job["gen"], why, job["finish"], job["abort"])
        except BaseException:
            traceback.print_exc()
        print("%s: %s" % (job["title"], "finished" if why is None else why), flush=True)
        return {"FINISHED"} if why is None else {"CANCELLED"}

    def modal(self, context, event):
        if event.type == "ESC" and event.value == "PRESS":
            return self._done(context, "cancelled (ESC)")
        if event.type != "TIMER":
            return {"RUNNING_MODAL"}                  # nothing else is allowed to touch the scene while it works
        t0 = time.time()
        try:
            while True:
                msg = next(_job()["gen"])
                self._n += 1
                if msg:
                    self._text(context, msg)
                if time.time() - t0 > BUDGET:
                    break
        except StopIteration:
            return self._done(context, None)
        except BaseException as e:                    # KeyboardInterrupt = the STOP file of the render script
            if not isinstance(e, KeyboardInterrupt):
                traceback.print_exc()
            return self._done(context, "stopped (%s)" % (e if isinstance(e, KeyboardInterrupt) else "error, see the system console"))
        return {"RUNNING_MODAL"}




def _job():
    """the running job; kept in bpy.app.driver_namespace so that it survives as_module() running this text again
    (only used in the interface: touching it in background mode made the bpy module crash when it shuts down)"""
    return bpy.app.driver_namespace.setdefault("uo_job", {})


def _register():
    old = getattr(bpy.types, "WM_OT_uo_job", None)
    if old is not None:
        try:
            bpy.utils.unregister_class(old)
        except Exception:
            pass
    bpy.utils.register_class(UO_OT_job)


def run(gen, title, finish=None, abort=None):
    """run the generator `gen` (see the top of the file); returns when it is over (background) or at once (window)"""
    if not bpy.app.background and _job():
        print("%s: another job is running (%s) - finish or cancel it with ESC first" % (title, _job()["title"]))
        return False
    if bpy.app.background or bpy.context.window is None:
        try:
            for _ in gen:
                pass
        except BaseException:
            _end(gen, "error", finish, abort)
            raise
        _end(gen, None, finish, abort)
        return True
    _register()
    _job().update(gen=gen, title=title, finish=finish, abort=abort)
    bpy.ops.wm.uo_job("INVOKE_DEFAULT")
    return True
