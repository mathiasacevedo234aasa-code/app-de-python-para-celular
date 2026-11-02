"""Motor de ejecución: corre el código del usuario en un hilo aparte,
redirige print()/input() a la consola del IDE y permite detenerlo."""
import builtins
import os
import queue
import sys
import threading
import traceback

from kivy.clock import Clock


CURRENT_STOP = threading.Event()  # evento de parada de la ejecución en curso


class StopExecution(BaseException):
    """Se lanza dentro del hilo del usuario cuando se pulsa Detener."""


class _Stream:
    def __init__(self, runner, is_err=False):
        self.runner = runner
        self.is_err = is_err

    def write(self, s):
        if s:
            self.runner._emit(s)
        return len(s)

    def flush(self):
        pass

    def isatty(self):
        return False


class Runner:
    def __init__(self, on_output, on_input_request, on_finish):
        self.on_output = on_output
        self.on_input_request = on_input_request
        self.on_finish = on_finish
        self.thread = None
        self.stop_event = threading.Event()
        self.input_queue = queue.Queue()
        self._buf = []
        self._lock = threading.Lock()
        self._flush_ev = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    # ---------- salida (agrupada para no saturar la UI) ----------
    def _emit(self, s):
        with self._lock:
            self._buf.append(s)
            if self._flush_ev is None:
                self._flush_ev = Clock.schedule_once(self._flush, 0.03)

    def _flush(self, *_):
        with self._lock:
            data = "".join(self._buf)
            self._buf.clear()
            self._flush_ev = None
        if data:
            self.on_output(data)

    # ---------- entrada ----------
    def _input(self, prompt=""):
        if prompt:
            self._emit(str(prompt))
        Clock.schedule_once(lambda dt: self.on_input_request(True), 0)
        while True:
            if self.stop_event.is_set():
                raise StopExecution()
            try:
                line = self.input_queue.get(timeout=0.1)
                break
            except queue.Empty:
                continue
        Clock.schedule_once(lambda dt: self.on_input_request(False), 0)
        self._emit(line + "\n")
        return line

    def send_input(self, text):
        self.input_queue.put(text)

    # ---------- ejecución ----------
    def run(self, code, filename):
        if self.running:
            return
        global CURRENT_STOP
        self.stop_event.clear()
        CURRENT_STOP = self.stop_event
        while not self.input_queue.empty():
            self.input_queue.get_nowait()
        self.thread = threading.Thread(target=self._worker, args=(code, filename), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        tk = sys.modules.get("tkinter")
        if tk is not None and hasattr(tk, "_shutdown"):
            tk._shutdown()

    def _tracer(self, frame, event, arg):
        if self.stop_event.is_set():
            raise StopExecution()
        return self._tracer

    def _worker(self, code, filename):
        old_out, old_err, old_input = sys.stdout, sys.stderr, builtins.input
        old_cwd = os.getcwd()
        folder = os.path.dirname(os.path.abspath(filename))
        sys.stdout = _Stream(self)
        sys.stderr = _Stream(self, True)
        builtins.input = self._input
        sys.path.insert(0, folder)
        status = 0
        tk = sys.modules.get("tkinter")
        if tk is not None and hasattr(tk, "_reset"):
            tk._reset(self.stop_event)
        try:
            os.chdir(folder)
            g = {"__name__": "__main__", "__file__": filename, "__builtins__": builtins}
            compiled = compile(code, filename, "exec")
            sys.settrace(self._tracer)
            exec(compiled, g)
            # Si el script creó ventanas tkinter pero no llamó mainloop(), las mantiene.
            tk = sys.modules.get("tkinter")
            if tk is not None and hasattr(tk, "_pending_mainloop"):
                tk._pending_mainloop()
        except StopExecution:
            status = 2
            self._emit("\n[Ejecución detenida]\n")
        except SystemExit as e:
            if e.code not in (None, 0):
                status = 1
        except BaseException:
            status = 1
            etype, evalue, tb = sys.exc_info()
            # Ocultar los marcos internos del IDE
            frames = traceback.extract_tb(tb)
            frames = [f for f in frames if f.filename == filename] or frames
            text = "Traceback (most recent call last):\n"
            text += "".join(traceback.format_list(frames))
            text += "".join(traceback.format_exception_only(etype, evalue))
            self._emit(text)
        finally:
            sys.settrace(None)
            tk = sys.modules.get("tkinter")
            if tk is not None and hasattr(tk, "_shutdown"):
                tk._shutdown()
            sys.stdout, sys.stderr, builtins.input = old_out, old_err, old_input
            try:
                sys.path.remove(folder)
            except ValueError:
                pass
            os.chdir(old_cwd)
            Clock.schedule_once(lambda dt: (self._flush(), self.on_finish(status)), 0.05)
