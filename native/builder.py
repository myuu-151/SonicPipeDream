"""Sonic Pipe Dream Builder: the Windows build from this repo, in a window.

    Double-click "Build Sonic Pipe Dream.bat" (or: python native/builder.py)

It checks what the build needs (Octave-libogc's source with its editor, Visual Studio with C++,
the Vulkan SDK) and says how to fix what's missing. Then one button compiles Octave's Windows
program (2 projects at a time, at low priority), packages the game with Octave -- its shaders,
every asset, the program named Sonic2Special3D.exe -- into proj/Packaged/Windows, and, if asked,
zips that up to share. Everything the game needs is in git.

Every step runs in the background, without a window of its own; the window shows each step's
progress, and of the output only the steps and errors ("Show every line" for the rest). All of
it is in proj/Intermediate/builder.log. The folder chosen is remembered in native/.builder.json
(not in git).
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from tkinter import filedialog, ttk

HERE = Path(__file__).resolve().parents[1]
PROJ = HERE / 'proj'
NAME = 'Sonic2Special3D'                       # the project's (proj/Sonic2Special3D.octp)
OUT = PROJ / 'Packaged' / 'Windows'
EXE = OUT / (NAME + '.exe')
PACKAGED = OUT / NAME
ZIP = PROJ / 'Packaged' / 'SonicPipeDream-Windows.zip'
SETTINGS = Path(__file__).with_name('.builder.json')
LOG_FILE = PROJ / 'Intermediate' / 'builder.log'
LOW_PRIORITY = 0x4000 | 0x08000000  # below normal, no console window (Windows)
SOURCE_LINE = re.compile(r'^\s*[\w.+-]+\.(?:cpp|c|cc)$')
# Octave's and MSBuild's chatter: never an error, even where it says so.
NOISE = re.compile(r'^(?:Asset (?:loaded|saved)|Unloading|Loading script|Cannot unload|Auto-parenting|\[Exec\]|'
                   r'Attempting to watch|Headless mode|Running EngineStartup|\(Octave\)|Begin packaging|'
                   r'Shutdown Complete|Failed to open file|Stream failed|_mkdir error|'
                   r'\s*\d+ [Ff]ile\(s\) (?:copied|moved)|The file cannot be copied|Compile Successful|'
                   r'The system cannot find the file|[A-Za-z]:[\\/])')
IMPORTANT = re.compile(r'\berror\b|unresolved external|\bfailed\b|Traceback|cannot open', re.IGNORECASE)


def default_folder(*names):
    """The first of these folders beside this repo (or beside its parent) that exists."""
    for base in (HERE.parent, HERE.parent.parent):
        for name in names:
            if (base / name).is_dir():
                return str(base / name)
    return str(HERE.parent / names[0])


def vswhere():
    for path in (Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft Visual Studio'
                 / 'Installer' / 'vswhere.exe',):
        if path.exists():
            return path
    return None


def find_msbuild(octave):
    """Visual Studio's MSBuild, with the C++ tools (vswhere: Visual Studio's own, or Octave's copy)."""
    tool = vswhere() or (Path(octave) / 'External' / 'vswhere' / 'vswhere.exe')
    if not tool.exists():
        return None
    try:
        out = subprocess.run([str(tool), '-latest', '-products', '*', '-requires',
                              'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-find',
                              r'MSBuild\**\Bin\MSBuild.exe'], capture_output=True, text=True,
                             creationflags=0x08000000 if os.name == 'nt' else 0).stdout.strip().splitlines()
    except OSError:
        return None
    return Path(out[0]) if out and Path(out[0]).exists() else None


def find_glslc():
    sdk = os.environ.get('VULKAN_SDK')
    if sdk and (Path(sdk) / 'Bin' / 'glslc.exe').exists():
        return Path(sdk)
    return None


def program_sources(octave):
    """The source files of Octave's Windows program and what it's built from (Standalone, the
    engine, the libraries they reference): what MSBuild could compile, for its progress."""
    seen, total, todo = set(), 0, [Path(octave) / 'Standalone' / 'Standalone.vcxproj']
    while todo:
        project = todo.pop().resolve()
        if project in seen or not project.exists():
            continue
        seen.add(project)
        try:
            root = ET.parse(project).getroot()
        except ET.ParseError:
            continue
        for item in root.iter():
            tag = item.tag.split('}')[-1]
            if tag == 'ClCompile' and item.get('Include'):
                total += 1
            elif tag == 'ProjectReference' and item.get('Include'):
                todo.append(project.parent / item.get('Include'))
    return total


def console_python():
    exe = Path(sys.executable)
    if exe.name.lower() == 'pythonw.exe' and exe.with_name('python.exe').exists():
        return str(exe.with_name('python.exe'))
    return str(exe)


class Builder:
    def __init__(self, root):
        self.root = root
        self.lines = queue.Queue()
        self.busy = False
        self.ready = False
        root.title('Sonic Pipe Dream Builder')
        root.minsize(660, 520)
        settings = {}
        try:
            settings = json.loads(SETTINGS.read_text())
        except (OSError, ValueError):
            pass
        self.octave = tk.StringVar(value=settings.get('octave', default_folder('octave-libogc', 'Octave-libogc')))
        self.make_zip = tk.BooleanVar(value=False)
        self.verbose = tk.BooleanVar(value=False)
        self.entries = []  # every line of output: (text, shown without "Show every line")
        self.phase = ''
        self.step = ''

        pad = {'padx': 10, 'pady': 4}
        ttk.Label(root, text='Sonic Pipe Dream for Windows', font=('Segoe UI', 14, 'bold')).pack(anchor='w', **pad)

        checks = ttk.LabelFrame(root, text='What the build needs')
        checks.pack(fill='x', **pad)
        self.rows = {}
        for key, title in (('octave', 'Octave-libogc'), ('vs', 'Visual Studio (C++)'), ('vulkan', 'Vulkan SDK')):
            row = ttk.Frame(checks)
            row.pack(fill='x', padx=6, pady=2)
            mark = ttk.Label(row, width=3, font=('Segoe UI', 11, 'bold'))
            mark.pack(side='left')
            ttk.Label(row, text=title, width=26).pack(side='left')
            note = ttk.Label(row, foreground='#555')
            note.pack(side='left', fill='x', expand=True)
            if key == 'octave':
                ttk.Button(row, text='Choose...', command=self.choose).pack(side='right')
            self.rows[key] = (mark, note)

        options = ttk.Frame(root)
        options.pack(fill='x', **pad)
        ttk.Checkbutton(options, text=f'Zip it to share ({ZIP.name})', variable=self.make_zip).pack(side='left')

        buttons = ttk.Frame(root)
        buttons.pack(fill='x', **pad)
        self.build_button = ttk.Button(buttons, text='Build Sonic Pipe Dream', command=self.build)
        self.build_button.pack(side='left')
        self.open_button = ttk.Button(buttons, text='Open the build folder', command=self.open_folder)
        self.open_button.pack(side='left', padx=8)
        self.progress = ttk.Progressbar(buttons, mode='indeterminate', length=240, maximum=100)  # while building

        self.status = ttk.Label(root, text='')
        self.status.pack(anchor='w', **pad)

        ttk.Checkbutton(root, text='Show every line', variable=self.verbose,
                        command=self.show_log).pack(anchor='w', padx=10)
        frame = ttk.Frame(root)
        frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.log = tk.Text(frame, height=14, wrap='none', font=('Consolas', 9), state='disabled')
        scroll = ttk.Scrollbar(frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.log.pack(side='left', fill='both', expand=True)

        self.check()
        self.update_open()
        root.after(100, self.pump)

    # --- what the build needs -------------------------------------------------

    def set_row(self, key, ok, note):
        mark, label = self.rows[key]
        mark.configure(text='OK' if ok else 'X', foreground='#1a7f37' if ok else '#c62828')
        label.configure(text=note)

    def check(self):
        ok = True
        octave = Path(self.octave.get())
        if not (octave / 'Octave.exe').exists():
            self.set_row('octave', False, f'no Octave.exe in {octave}')
            ok = False
        elif not (octave / 'Octave.sln').exists() or not (octave / 'Standalone' / 'Standalone.vcxproj').exists():
            self.set_row('octave', False, "no Octave.sln and Standalone/ in it: the Windows build needs Octave's source")
            ok = False
        else:
            self.set_row('octave', True, str(octave))
        self.msbuild = find_msbuild(octave)
        if self.msbuild:
            self.set_row('vs', True, str(self.msbuild.parents[3]))
        else:
            self.set_row('vs', False, 'install Visual Studio with "Desktop development with C++"')
            ok = False
        self.vulkan = find_glslc()
        if self.vulkan:
            self.set_row('vulkan', True, str(self.vulkan))
        else:
            self.set_row('vulkan', False, 'install the Vulkan SDK (vulkan.lunarg.com): it compiles the shaders')
            ok = False
        self.ready = ok
        self.build_button.configure(state='normal' if ok and not self.busy else 'disabled')
        self.status.configure(text='Ready to build.' if ok else 'Fix the X items above, then build.')
        return ok

    def choose(self):
        folder = filedialog.askdirectory(title='The Octave-libogc folder', initialdir=self.octave.get() or str(HERE.parent))
        if folder:
            self.octave.set(folder)
            try:
                SETTINGS.write_text(json.dumps({'octave': self.octave.get()}))
            except OSError:
                pass
            self.check()

    # --- the window's log and progress -------------------------------------

    def write(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text)
        self.log.see('end')
        self.log.configure(state='disabled')

    def show_log(self):
        """The log again, every line or only those that matter."""
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.insert('end', ''.join(text + '\n' for text, shown in self.entries if shown or self.verbose.get()))
        self.log.see('end')
        self.log.configure(state='disabled')

    def pump(self):
        try:
            while True:
                kind, *rest = self.lines.get_nowait()
                if kind == 'line':
                    text, shown = rest
                    self.entries.append((text, shown))
                    if shown or self.verbose.get():
                        self.write(text + '\n')
                elif kind == 'phase':
                    self.phase = rest[0]
                    self.show_step('starting')
                elif kind == 'step':
                    self.show_step(rest[0])
                elif kind == 'progress':
                    self.show_progress(*rest)
                elif kind == 'count':
                    self.status.configure(text=f'{self.phase}: {self.step}, {rest[0]} files compiled')
                elif kind == 'done':
                    self.finished(*rest)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def show_step(self, step):
        """A step without a count yet: the bar moves to show it's working."""
        self.step = step
        self.progress.stop()
        self.progress.configure(mode='indeterminate')
        self.progress.start(12)
        self.status.configure(text=f'{self.phase}: {step}...')

    def show_progress(self, done, total):
        if str(self.progress.cget('mode')) != 'determinate':
            self.progress.stop()
            self.progress.configure(mode='determinate')
        percent = 100 * done // max(total, 1)
        self.progress.configure(value=percent)
        self.status.configure(text=f'{self.phase}: {self.step}, {done} of {total} ({percent}%)')

    def say(self, text):
        """A line of the builder's own, always shown."""
        self.lines.put(('line', text, True))
        with open(LOG_FILE, 'a', encoding='utf-8') as log:
            log.write(text + '\n')

    # --- building ---------------------------------------------------------

    def build(self):
        if self.busy or not self.check():
            return
        self.busy = True
        self.build_button.configure(state='disabled')
        self.progress.pack(side='right')
        self.status.configure(foreground='')
        self.entries = []
        self.show_log()
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text('', encoding='utf-8')
        threading.Thread(target=self.run_build, daemon=True).start()

    def run(self, args, cwd, env, watch):
        """Runs a step hidden, in the background at low priority (what it starts inherits that);
        each line of its output to the log file, and to watch, which says whether the window shows
        it (and may note a step or progress). True if it succeeded."""
        startup = None
        if os.name == 'nt':
            # Started hidden: Octave makes its window even when headless.
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0  # SW_HIDE
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, startupinfo=startup,
                                creationflags=LOW_PRIORITY if os.name == 'nt' else 0)
        with open(LOG_FILE, 'a', encoding='utf-8') as log:
            for raw in proc.stdout:
                text = raw.decode('utf-8', 'replace').rstrip('\r\n').split('\r')[-1].rstrip()
                if not text:
                    continue
                log.write(text + '\n')
                self.lines.put(('line', text, watch(text)))
        return proc.wait() == 0

    def env(self):
        """Visual Studio's compiler kept to 2 processes (CL_MPCount, which MSBuild reads from the
        environment, for any project that compiles in parallel)."""
        return dict(os.environ, CL_MPCount='2', VULKAN_SDK=str(self.vulkan))

    def compile_program(self, octave):
        """Octave's Windows program (Standalone, Release|x64), with MSBuild: 2 projects at a time.
        Octave's packaging builds it too, through Visual Studio, which would use every core; built
        here first, that finds it up to date."""
        # 526: what a whole build of it compiles (measured), more than the projects list; when it's
        # been built before, only what changed, so then just counted
        objects = octave / 'Engine' / 'Intermediate' / 'Windows' / 'x64' / 'Release'
        total = 0 if objects.is_dir() and any(objects.rglob('*.obj')) else 526
        count = {'done': 0}
        self.lines.put(('step', "compiling Octave's Windows program"))

        def watch(text):
            if SOURCE_LINE.match(text):
                count['done'] += 1
                if total:
                    self.lines.put(('progress', min(count['done'], total), max(total, count['done'])))
                else:
                    self.lines.put(('count', count['done']))
                return False
            return bool(IMPORTANT.search(text)) and 'warning' not in text.lower()
        return self.run([str(self.msbuild), 'Octave.sln', '/t:Standalone', '/p:Configuration=Release',
                         '/p:Platform=x64', '/m:2', '/v:m', '/nologo'], octave, self.env(), watch)

    def watch_packaging(self, started, stop):
        """The assets Octave has written so far, of the project's, are the packaging's progress."""
        total = sum(1 for _ in (PROJ / 'Assets').rglob('*.oct'))
        named = False
        while not stop.is_set():
            done = 0
            if PACKAGED.is_dir():
                for path in PACKAGED.rglob('*.oct'):
                    try:
                        done += path.stat().st_mtime >= started
                    except OSError:
                        pass
            if done and not named:
                named = True
                self.lines.put(('step', 'packaging the assets'))
            if done:
                self.lines.put(('progress', min(done, total), total))
            if done >= total:
                self.lines.put(('step', "copying in the program"))
                return
            stop.wait(1.5)

    def package(self, octave):
        """Octave's packaging: the shaders compiled, the assets packaged, the program copied in.
        Octave's own lines come in blocks, late (its "Compiling game executable" after it's all
        done), so the progress is the assets it has written, counted as they appear."""
        started, stop = time.time() - 2, threading.Event()
        # (copied, the program keeps its build's time: so the old one goes first, and a program
        # there afterwards is this packaging's)
        try:
            EXE.unlink()
        except OSError:
            pass
        self.lines.put(('step', 'compiling the shaders, then packaging the assets'))
        threading.Thread(target=self.watch_packaging, args=(started, stop), daemon=True).start()

        def watch(text):
            return bool(IMPORTANT.search(text)) and not NOISE.match(text)
        try:
            self.run([str(octave / 'Octave.exe'), '-headless', '-project', (PROJ / (NAME + '.octp')).as_posix(),
                      '-build', 'Windows'], octave, self.env(), watch)
        finally:
            stop.set()
        return EXE.exists()

    def zip_it(self):
        """proj/Packaged/Windows as SonicPipeDream/ in a zip, to share."""
        self.lines.put(('step', 'zipping it'))
        files = [f for f in OUT.rglob('*') if f.is_file()]
        tmp = ZIP.with_suffix('.zip.tmp')
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for n, f in enumerate(files, 1):
                z.write(f, 'SonicPipeDream/' + f.relative_to(OUT).as_posix())
                if n % 25 == 0 or n == len(files):
                    self.lines.put(('progress', n, len(files)))
        tmp.replace(ZIP)
        self.say(f'zipped: {ZIP} ({ZIP.stat().st_size / 1048576:.0f} MB)')
        return True

    def run_build(self):
        octave = Path(self.octave.get())
        self.say("== Compiling Octave's Windows program")
        self.lines.put(('phase', 'Compiling'))
        ok = self.compile_program(octave)
        if ok:
            self.say('== Packaging the game with Octave')
            self.lines.put(('phase', 'Packaging'))
            ok = self.package(octave)
        if ok and self.make_zip.get():
            self.lines.put(('phase', 'Sharing'))
            try:
                ok = self.zip_it()
            except OSError as e:
                self.say(f'could not zip it: {e}')
                ok = False
        self.lines.put(('done', ok))

    def finished(self, ok):
        self.busy = False
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0)
        self.progress.pack_forget()
        self.build_button.configure(state='normal' if self.ready else 'disabled')
        if ok:
            self.status.configure(text=f'Done: {EXE}', foreground='#1a7f37')
            self.entries.append((f'== Done: {EXE}', True))
            self.write(f'== Done: {EXE}\n')
        else:
            self.status.configure(text=f'The build failed: the log says why (all of it: {LOG_FILE}).',
                                  foreground='#c62828')
            if not self.verbose.get():
                hidden = [text for text, shown in self.entries if not shown][-25:]
                if hidden:
                    self.write('\n-- the last lines of output:\n' + ''.join(text + '\n' for text in hidden))
        self.update_open()

    def update_open(self):
        self.open_button.configure(state='normal' if EXE.exists() else 'disabled')

    def open_folder(self):
        if EXE.exists():
            subprocess.Popen(['explorer', '/select,', str(ZIP if ZIP.exists() and self.make_zip.get() else EXE)])


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use('vista')
    except tk.TclError:
        pass
    Builder(root)
    root.mainloop()


if __name__ == '__main__':
    main()
