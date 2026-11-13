"""Automatic headless Linux Qt shim builder & pre-loader.

On fresh Linux environments without system OpenGL/EGL/dbus libraries
(``libGL.so.1``, ``libEGL.so.1``, ``libxkbcommon.so.0``,
``libdbus-1.so.3``), PySide6 cannot load the Qt platform plugin. This module
self-heals by compiling minimal symbol-matched C stub shims into
``.venv/qt_shims/`` and *pre-loading* them via ``ctypes`` before any PySide6
import (mid-process ``LD_LIBRARY_PATH`` changes do not affect the dynamic
loader, so pre-loading is required). No-op on Windows.

Called automatically by ``tests/conftest.py`` and ``nexus_ultron/cli.py``.
Existing working shims are never clobbered: shims are only compiled when a
corresponding ``.so`` is missing.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Comprehensive minimal C stub sources. libdbus-1 exports every symbol that
# PySide6's libQt6DBus requires, tagged with the LIBDBUS_1_3 version via the
# accompanying .map version script.
# ---------------------------------------------------------------------------

LIBDBUS_C = r"""/* Auto-generated minimal libdbus-1 shim for headless offscreen Qt. */
#include <stddef.h>

int dbus_bus_add_match(void* connection, const char* rule, void* error) { return 0; }
void* dbus_bus_get_private(int bus_type) { return NULL; }
const char* dbus_bus_get_unique_name(void* connection) { return NULL; }
int dbus_bus_register(void* connection, void* error) { return 0; }
int dbus_bus_remove_match(void* connection, const char* rule, void* error) { return 0; }
int dbus_connection_add_filter(void* connection, void* function, void* user_data, void* free_function) { return 0; }
int dbus_connection_can_send_type(void* connection, int type) { return 0; }
void dbus_connection_close(void* connection) { return; }
int dbus_connection_dispatch(void* connection) { return 0; }
int dbus_connection_get_is_authenticated(void* connection) { return 0; }
int dbus_connection_get_is_connected(void* connection) { return 0; }
void* dbus_connection_open_private(const char* address) { return NULL; }
void* dbus_connection_ref(void* connection) { return NULL; }
int dbus_connection_send(void* connection, void* message, void* serial) { return 0; }
int dbus_connection_send_with_reply(void* connection, void* message, void* pending, int timeout) { return 0; }
int dbus_connection_set_allow_anonymous(void* connection, int allow_anonymous) { return 0; }
int dbus_connection_set_dispatch_status_function(void* connection, void* function, void* user_data, void* free_function) { return 0; }
int dbus_connection_set_exit_on_disconnect(void* connection, int exit_on_disconnect) { return 0; }
int dbus_connection_set_timeout_functions(void* connection, void* add, void* remove, void* toggle, void* user_data, void* free_function) { return 0; }
int dbus_connection_set_watch_functions(void* connection, void* add, void* remove, void* toggle, void* user_data, void* free_function) { return 0; }
void dbus_connection_unref(void* connection) { return; }
void dbus_error_free(void* error) { return; }
void dbus_error_init(void* error) { return; }
int dbus_error_is_set(void* error) { return 0; }
void dbus_free(void* memory) { return; }
int dbus_get_local_machine_id(char* buffer, int length) { return 0; }
void* dbus_message_copy(void* message) { return NULL; }
int dbus_message_get_allow_interactive_authorization(void* message) { return 0; }
const char* dbus_message_get_error_name(void* message) { return NULL; }
const char* dbus_message_get_interface(void* message) { return NULL; }
const char* dbus_message_get_member(void* message) { return NULL; }
int dbus_message_get_no_reply(void* message) { return 0; }
const char* dbus_message_get_path(void* message) { return NULL; }
const char* dbus_message_get_sender(void* message) { return NULL; }
unsigned int dbus_message_get_serial(void* message) { return 0; }
const char* dbus_message_get_signature(void* message) { return NULL; }
int dbus_message_get_type(void* message) { return 0; }
int dbus_message_iter_append_basic(void* iter, int type, const void* value) { return 0; }
int dbus_message_iter_append_fixed_array(void* iter, int element_type, const void* value, int n_elements) { return 0; }
void dbus_message_iter_close_container(void* iter, void* sub) { return; }
int dbus_message_iter_get_arg_type(void* iter) { return 0; }
int dbus_message_iter_get_basic(void* iter, void* value) { return 0; }
int dbus_message_iter_get_element_type(void* iter) { return 0; }
int dbus_message_iter_get_fixed_array(void* iter, void* value, int* n_elements) { return 0; }
const char* dbus_message_iter_get_signature(void* iter) { return NULL; }
int dbus_message_iter_init(void* message, void* iter) { return 0; }
int dbus_message_iter_init_append(void* message, void* iter) { return 0; }
int dbus_message_iter_next(void* iter) { return 0; }
int dbus_message_iter_open_container(void* iter, int type, const char* signature, void* sub) { return 0; }
int dbus_message_iter_recurse(void* iter, void* sub) { return 0; }
void* dbus_message_new(int type) { return NULL; }
void* dbus_message_new_method_call(const char* bus, const char* path, const char* interface, const char* method) { return NULL; }
void* dbus_message_new_signal(const char* path, const char* interface, const char* name) { return NULL; }
void* dbus_message_ref(void* message) { return NULL; }
int dbus_message_set_allow_interactive_authorization(void* message, int allow) { return 0; }
int dbus_message_set_auto_start(void* message, int auto_start) { return 0; }
int dbus_message_set_destination(void* message, const char* destination) { return 0; }
int dbus_message_set_error_name(void* message, const char* error_name) { return 0; }
int dbus_message_set_no_reply(void* message, int no_reply) { return 0; }
int dbus_message_set_path(void* message, const char* path) { return 0; }
int dbus_message_set_reply_serial(void* message, unsigned int serial) { return 0; }
int dbus_message_set_sender(void* message, const char* sender) { return 0; }
void dbus_message_unref(void* message) { return; }
int dbus_pending_call_block(void* pending) { return 0; }
void dbus_pending_call_cancel(void* pending) { return; }
int dbus_pending_call_get_completed(void* pending) { return 0; }
int dbus_pending_call_set_notify(void* pending, void* function, void* user_data, void* free_function) { return 0; }
void* dbus_pending_call_steal_reply(void* pending) { return NULL; }
void dbus_pending_call_unref(void* pending) { return; }
int dbus_server_allocate_data_slot(void) { return 0; }
void dbus_server_disconnect(void* server) { return; }
void dbus_server_free_data_slot(int slot) { return; }
const char* dbus_server_get_address(void* server) { return NULL; }
int dbus_server_get_is_connected(void* server) { return 0; }
int dbus_server_listen(const char* address) { return 0; }
int dbus_server_set_data(void* server, int slot, void* data, void* free_function) { return 0; }
int dbus_server_set_new_connection_function(void* server, void* function, void* user_data, void* free_function) { return 0; }
int dbus_server_set_timeout_functions(void* server, void* add, void* remove, void* toggle, void* user_data, void* free_function) { return 0; }
int dbus_server_set_watch_functions(void* server, void* add, void* remove, void* toggle, void* user_data, void* free_function) { return 0; }
void dbus_server_unref(void* server) { return; }
void dbus_shutdown(void) { return; }
int dbus_threads_init_default(void) { return 0; }
int dbus_timeout_get_enabled(void* timeout) { return 0; }
int dbus_timeout_get_interval(void* timeout) { return 0; }
int dbus_timeout_handle(void* timeout) { return 0; }
int dbus_watch_get_enabled(void* watch) { return 0; }
unsigned int dbus_watch_get_flags(void* watch) { return 0; }
int dbus_watch_get_unix_fd(void* watch) { return 0; }
int dbus_watch_handle(void* watch) { return 0; }
"""

LIBDBUS_MAP = "LIBDBUS_1_3 {\n  global:\n    *;\n  local:\n    *;\n};\n"

SHIM_SOURCES: dict[str, str] = {
    "libGL.so.1.c": r"""
void* __shim_zero(void) { return 0; }
long glBindTexture(void) { return 0; }
long glBlendFunc(void) { return 0; }
long glClear(void) { return 0; }
long glDeleteTextures(void) { return 0; }
long glDisable(void) { return 0; }
long glEnable(void) { return 0; }
long glGenTextures(void) { return 0; }
long glGetIntegerv(void) { return 0; }
long glGetString(void) { return 0; }
long glLoadIdentity(void) { return 0; }
long glLoadMatrixf(void) { return 0; }
long glMatrixMode(void) { return 0; }
long glOrtho(void) { return 0; }
long glPixelStorei(void) { return 0; }
long glTexImage2D(void) { return 0; }
long glTexParameterf(void) { return 0; }
long glTexParameteri(void) { return 0; }
long glTexSubImage2D(void) { return 0; }
long glViewport(void) { return 0; }
long glXChooseFBConfig(void) { return 0; }
long glXChooseVisual(void) { return 0; }
long glXCreateContext(void) { return 0; }
long glXCreateNewContext(void) { return 0; }
long glXDestroyContext(void) { return 0; }
long glXGetConfig(void) { return 0; }
long glXGetFBConfigAttrib(void) { return 0; }
long glXGetProcAddressARB(void) { return 0; }
long glXGetVisualFromFBConfig(void) { return 0; }
long glXMakeCurrent(void) { return 0; }
""",
    "libEGL.so.1.c": r"""
void* __shim_zero(void) { return 0; }
long eglBindAPI(void) { return 0; }
long eglChooseConfig(void) { return 0; }
long eglCreateContext(void) { return 0; }
long eglCreatePbufferSurface(void) { return 0; }
long eglCreateWindowSurface(void) { return 0; }
long eglDestroyContext(void) { return 0; }
long eglDestroySurface(void) { return 0; }
long eglGetConfigAttrib(void) { return 0; }
long eglGetConfigs(void) { return 0; }
long eglGetCurrentContext(void) { return 0; }
long eglGetCurrentDisplay(void) { return 0; }
long eglGetCurrentSurface(void) { return 0; }
long eglGetDisplay(void) { return 0; }
long eglGetError(void) { return 0; }
long eglGetProcAddress(void) { return 0; }
long eglInitialize(void) { return 0; }
long eglMakeCurrent(void) { return 0; }
long eglQueryContext(void) { return 0; }
long eglQueryString(void) { return 0; }
long eglQuerySurface(void) { return 0; }
long eglSwapBuffers(void) { return 0; }
long eglSwapInterval(void) { return 0; }
long eglTerminate(void) { return 0; }
""",
    "libxkbcommon.so.0.c": r"""
int xkb_context_new(int flags) { return 0; }
void xkb_context_unref(void* ctx) { return; }
int xkb_keymap_new_from_names(void* ctx, void* names, int flags) { return 0; }
void xkb_keymap_unref(void* km) { return; }
int xkb_state_new(void* km) { return 0; }
void xkb_state_unref(void* state) { return; }
int xkb_state_key_get_syms(void* state, int key, void* syms, int n_syms) { return 0; }
""",
    "libdbus-1.so.3.c": LIBDBUS_C,
}

SHIM_LIBRARIES: dict[str, str] = {
    "libGL.so.1": "libGL.so.1.c",
    "libEGL.so.1": "libEGL.so.1.c",
    "libxkbcommon.so.0": "libxkbcommon.so.0.c",
    "libdbus-1.so.3": "libdbus-1.so.3.c",
}

SHIM_MAPS: dict[str, str | None] = {
    "libdbus-1.so.3": LIBDBUS_MAP,
}


def _find_venv_root(repo_root: Path) -> Path | None:
    """Locate the active virtualenv root."""
    candidates = [repo_root / ".venv", Path(sys.prefix)]
    for c in candidates:
        if c.exists() and (c / "pyvenv.cfg").exists():
            return c.resolve()
    return None


def _compile_shim(cc: str, shim_dir: Path, lib_name: str, src_name: str) -> bool:
    out_path = shim_dir / lib_name
    src_path = shim_dir / src_name
    src_path.write_text(SHIM_SOURCES[src_name], encoding="utf-8")
    cmd = [cc, "-shared", "-fPIC", "-o", str(out_path), str(src_path), "-Wl,-soname," + lib_name]
    map_text = SHIM_MAPS.get(lib_name)
    if map_text:
        map_path = shim_dir / (lib_name + ".map")
        map_path.write_text(map_text, encoding="utf-8")
        cmd.insert(-1, f"-Wl,--version-script={map_path}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        out_path.chmod(0o755)
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        sys.stderr.write(f"[qt_shim_builder] failed to compile {lib_name}: {exc}\n")
        return False


def ensure_qt_shims(repo_root: Path | None = None) -> Path | None:
    """Ensure headless Qt shims exist and are pre-loaded via ctypes.

    Returns the shim directory on Linux (whether just built or already
    present), or None on Windows. Existing working shims are never rebuilt.
    """
    if sys.platform != "linux":
        return None

    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent

    venv = _find_venv_root(repo_root)
    if venv is None:
        return None

    shim_dir = venv / "qt_shims"
    shim_dir.mkdir(parents=True, exist_ok=True)

    missing = [lib for lib in SHIM_LIBRARIES if not (shim_dir / lib).exists()]
    if missing:
        cc = "gcc" if subprocess.run(["which", "gcc"], capture_output=True).returncode == 0 else "cc"
        for lib_name in missing:
            _compile_shim(cc, shim_dir, lib_name, SHIM_LIBRARIES[lib_name])

    # Pre-load every shim by absolute path so the dynamic linker has them
    # available before PySide6 is imported (os.environ LD_LIBRARY_PATH changes
    # mid-process are not honoured by the loader for subsequently imported
    # extension modules).
    loaded = []
    for lib_name in SHIM_LIBRARIES:
        so_path = shim_dir / lib_name
        if so_path.exists():
            try:
                ctypes.CDLL(str(so_path))
                loaded.append(lib_name)
            except OSError as exc:
                sys.stderr.write(f"[qt_shim_builder] failed to preload {lib_name}: {exc}\n")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return shim_dir if loaded else None
