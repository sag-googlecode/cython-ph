VERSION_MAJOR  = 1
VERSION_MIN    = 0
VERSION_REV    = 0

import subprocess
import traceback
import shutil
import glob
import time
import imp
import sys
import os
sys.dont_write_bytecode = True


class WindowsPlatform(object):
    platform_name = 'windows'
    platform_identifier = 'win'
    shared_ext = 'dll'
    binary_ext = 'exe'


class LinuxPlatform(object):
    platform_name = 'linux'
    platform_identifier = 'linux'
    shared_ext = 'so'
    binary_ext = ''

    @staticmethod
    def pythonInclude():
        return '/usr/include/python2.7/'

    @staticmethod
    def pythonLib():
        return 'python2.7'

    @staticmethod
    def pythonLibDir():
        return None

    @staticmethod
    def compile(sourceFile, outputFile, includes = [], libraries = [], libraryDirs = [], language = 'c', shared = False):
        cmd = ''
        cmd += 'gcc '
        cmd += '%s ' % sourceFile
        cmd += '-o %s ' % outputFile
        if shared:
            cmd += '-shared -fPIC '
        for include in includes:
            if include:
                cmd += '-I%s ' % include
        for library in libraries:
            if library:
                cmd += '-l%s ' % library
        for libraryDir in libraryDirs:
            if libraryDir:
                cmd += '-L%s ' % libraryDir
        cmd = cmd[:-1]
        return cmd


class MacPlatform(object):
    platform_name = 'mac'
    platform_identifier = 'darwin'
    shared_ext = 'dylib'
    binary_ext = ''


class Backend(object):
    DefaultFilename = 'project.ph'

    platforms = [
        WindowsPlatform,
        LinuxPlatform,
        MacPlatform,
    ]

    @staticmethod
    def getPlatform(byName):
        for platform in Backend.platforms:
            if platform.platform_name == byName:
                return platform

    @staticmethod
    def isPlatform(platformName):
        name = Backend.getPlatform(platformName).platform_identifier
        if sys.platform.startswith(name):
            return True
        else:
            return False

    @staticmethod
    def thisPlatform():
        for platform in Backend.platforms:
            if Backend.isPlatform(platform.platform_name):
                return platform

    @staticmethod
    def paths(project, *paths):
        newPaths = []
        for path in paths:
            if path:
                if path.startswith('./'):
                    path = path[2:] #- Assume all paths without a leading slash
                    #- are relative paths

                if path.startswith('/') and sys.platform.startswith('win'):
                    # Convert a /c/myFolder/path into C:/myFolder/path
                    path = path[1:] #- Strip the first slash
                    path = path[0].upper() + ':' + path[1:] #- convert c to C:
                elif project.config['path']:
                    #- Convert src/foo/bar to /projectDir/src/foo/bar
                    path = project.config['path'] + '/' + path

                #- Swap out slashes for Windows
                if sys.platform.startswith('win'):
                    path = path.replace('/', '\\') #- Replace backslash with forward
                newPaths.append(path)
        return newPaths


    @staticmethod
    def compile(sourceFile, outputFile = None, includes = [], libraries = [], libraryDirs = [], language = 'c'):
        if hasattr(Backend.thisPlatform(), 'compile'):
            return Backend.thisPlatform().compile(sourceFile, outputFile, includes, libraries, libraryDirs, language)
        else:
            raise NotImplementedError('Unsupported compilation platform..')

    @staticmethod
    def cython(project, sourceFile, outputName = None, includeDirs = [], directives = {}, timestamps = False, force = False, quiet = False, verbose = False, embedPositions = False, cleanup = False, gdb = False, noDocstrings = False, annotate = False, lineDirectives = False, cplus = False, embed = False, python2 = False, python3 = False, fastFail = False, warningError = False, warningExtra = False):

        # Make file path's relative and convert slashes to Windows slashes
        sourceFile = Backend.paths(project, sourceFile)[0]
        includeDirs = Backend.paths(project, *includeDirs)

        cmd = ''
        cmd += 'cython '
        for incl in includeDirs:
            cmd += '-I %s' % incl
        if timestamps:     cmd += '-t '
        if force:          cmd += '-f '
        if quiet:          cmd += '-q '
        if verbose:        cmd += '-v '
        if embedPositions: cmd += '-p '
        if cleanup:        cmd += '--cleanup %s ' % int(cleanup)
        if gdb:            cmd += '--gdb '
        if noDocstrings:   cmd += '-D '
        if annotate:       cmd += '-a '
        if lineDirectives: cmd += '--line-directives '
        if cplus:          cmd += '--cplus'
        if embed:
            if embed == True:
                cmd += '--embed '
            else:
                cmd += '--embed %s ' % embed
        if python2:        cmd += '-2 '
        if python3:        cmd += '-3 '
        if fastFail:       cmd += '--fast-fail '
        if warningError:   cmd += '--warning-error '
        if warningExtra:   cmd += '--warning-extra '
        if len(directives) > 0:
            cmd += '-X '
            for key, value in directives.items():
                cmd += '%s=%s ' % (key, value)
        cmd += '%s' % sourceFile

        buildSeq = []
        buildSeq.append(cmd)

        cFile =  os.path.splitext(os.path.basename(sourceFile))[0]
        cFile += '.c'
        cOutFile = os.path.splitext(os.path.basename(outputName))[0]

        if embed:
            cOutFile += Backend.binaryExt()
        else:
            cOutFile += Backend.sharedExt()
        cmd = Backend.compile(cFile, cOutFile, includes = [Backend.pythonInclude()], libraries = [Backend.pythonLib()], libraryDirs = [Backend.pythonLibDir()])
        buildSeq.append(cmd)
        return buildSeq

    @staticmethod
    def delete(globPath):
        for filePath in glob.glob(globPath):
            if os.path.exists(filePath):
                if os.path.isdir(filePath):
                    shutil.rmtree(filePath)
                elif os.path.isfile(filePath):
                    os.remove(filePath)

    @staticmethod
    def sharedExt():
        return Backend.thisPlatform().shared_ext

    @staticmethod
    def binaryExt():
        return Backend.thisPlatform().binary_ext

    @staticmethod
    def pythonInclude():
        return Backend.thisPlatform().pythonInclude()

    @staticmethod
    def pythonLib():
        return Backend.thisPlatform().pythonLib()

    @staticmethod
    def pythonLibDir():
        return Backend.thisPlatform().pythonLibDir()


class CommandDispatcher(object):
    def __init__(self):
        #(cmd1, cmd2, cmd3): 0,1,2
        self.commands = {}

        #(cmd1, cmd2, cmd3): currentProc
        self.activeCommands = {}

    def add(self, command):
        assert type(command) == tuple
        self.commands[command] = 0

    def needDispatch(self):
        for command, n in self.commands.items():
            if len(command)-1 >= n:
                return True
        return False

    def dispatch(self):
        while self.needDispatch():
            for command, n in self.commands.items():
                # Add new processes
                if command not in self.activeCommands:
                    self.activeCommands[command] = subprocess.Popen(command[n], shell = True)
                    print command[n]
                    #print 'add', command[n]

                for command, process in self.activeCommands.items():
                    ret = process.poll()
                    if ret != None:
                        self.commands[command] += 1
                        del self.activeCommands[command]
                        #print 'finish', command[n]
            time.sleep(0.01) #- Small delay to stop CPU bogging

#cd = CommandDispatcher()
#cd.add(('sleep 1', 'sleep 2', 'sleep 3'))
#cd.dispatch()

class Project(object):
    def __init__(self, ph):
        self.ph = ph

        self.config = {
            'name': None,
            'version': None,
            'description': None,
            'link': None,
            'options': None,
            'path': '',
        }

    def setName(self, name):
        self.config['name'] = unicode(name)

    def setVersion(self, *args):
        if len(args) == 1:
            self.config['version'] = unicode(args[0])
        else:
            for supposedVersionNumber in args:
                try:
                    long(supposedVersionNumber)
                except:
                    ph.log('Invalid version number in call to ProjectVersion()')
                    exit()
            self.config['version'] = args

    def setDescription(self, description):
        self.config['description'] = unicode(description)

    def setLink(self, link):
        self.config['link'] = unicode(link)

    def setOptions(self, options):
        assert type(options) == dict
        for key, value in options.items():
            assert type(key) == str or type(key) == unicode, 'Option name must be a string or unicode object!'
            assert type(value) == str or type(value) == unicode, 'Option description must be a string or unicode object!'
        self.config['options'] = options

    def listOptions(self):
        for option, description in self.config['options'].items():
            ph.log('[--%s:value] %s' % (option, description))
        ph.log()

    def logInformation(self):
        name = self.config['name']
        version = self.config['version']
        description = self.config['description']
        link = self.config['link']

        if name:
            if version:
                ph.log('%s version %s' % (name, ph.versionString(version)))
            else:
                ph.log('%s' % name)

        if link:
            ph.log(link)

        if description:
            for line in description.splitlines():
                ph.log(line)
            ph.log()

    def loadFile(self, projectFile):
        '''
            Import the Python module by file path
        '''
        try:
            self.module = imp.load_source('project', projectFile)
        except Exception as e:
            ph.log('Error inside the project file \'%s\'' % projectFile)
            ph.log()
            for line in traceback.format_exc(e).splitlines():
                ph.log(line)
            exit()
        ph.log('Loaded project file \'%s\'' % projectFile)
        ph.log()
        self.config['path'] = os.path.dirname(self.module.__file__)

    def run(self):
        try:
            self.module.run()
        except Exception as e:
            ph.log()
            for line in traceback.format_exc(e).splitlines():
                ph.log(line)
            exit()





class ph(object):
    @staticmethod
    def versionString(*version):
        nVersion = ''
        for part in version:
            nVersion += str(part) + '.'
        version = nVersion.rstrip('.')
        return version

    @staticmethod
    def log(msg = ''):
        print ':ph: ' + msg

    @staticmethod
    def usage():
        ph.log('Usage: %s %s [--option:value]' % (Backend.DefaultFilename, sys.argv[0]))


    def __init__(self):
        ph.log('Project Helper, a Cython project build system')
        ph.log('Version %s' % self.versionString(VERSION_MAJOR, VERSION_MIN, VERSION_REV))
        ph.log()

        self.commandDispatcher = CommandDispatcher()
        self.commandLineArguments = {
            'name': sys.argv[0],
            'projectFile': None,
            'options': {},
        }

        for arg in sys.argv[1:]:
            if not os.path.isfile(Backend.DefaultFilename):
                if arg == '--help' or arg == '-h':
                    ph.usage()
                    exit()

            if arg.startswith('--'):
                if arg.startswith('--'):
                    if ':' in arg:
                        split = arg[len('--'):].split(':')
                        option, value = split[0], split[1]
                        self.commandLineArguments['options'][option] = value
                    else:
                        option = arg[len('--'):]
                        self.commandLineArguments['options'][option] = 'on'
            else:
                self.commandLineArguments['projectFile'] = arg

        self.project = Project(self)

        __builtins__.options = self.commandLineArguments['options']
        __builtins__.cython = self.cython
        __builtins__.delete = Backend.delete
        __builtins__.dispatch = self.commandDispatcher.dispatch
        __builtins__.PlatformBinaryExtension = Backend.binaryExt
        __builtins__.PlatformLibraryExtension = Backend.sharedExt
        __builtins__.ProjectName = self.project.setName
        __builtins__.ProjectVersion = self.project.setVersion
        __builtins__.ProjectDescription = self.project.setDescription
        __builtins__.ProjectLink = self.project.setLink
        __builtins__.ProjectOptions = self.project.setOptions
        __builtins__.SetOption = self.setOption
        __builtins__.GetOption = self.getOption
        __builtins__.log = ph.log


        projectFile = self.locateProjectFile()
        self.project.loadFile(projectFile)
        self.project.logInformation()

        opts = self.commandLineArguments['options']
        if (len(opts) == 0) or ('help' in opts):
            self.project.listOptions()
        else:
            self.project.run()

        #cd.add(('sleep 1', 'sleep 2', 'sleep 3'))
        self.commandDispatcher.dispatch()

    def cython(self, *args, **kwargs):
        cmds = Backend.cython(self.project, *args, **kwargs)
        self.commandDispatcher.add(tuple(cmds))

    def locateProjectFile(self):
        '''
            Unless specified as a paremeter to the program itself, assume
            that it's in the current directory named "project.ph"
        '''
        projectFile = self.commandLineArguments['projectFile']
        if projectFile:
            if os.path.isfile(projectFile):
                return projectFile
            else:
                ph.usage()
                ph.log()
                ph.log('Invalid project file was specified \'%s\'.' % projectFile)
                ph.log()
                ph.log('Specify it on the command line, e.g: %s project.ph' % sys.argv[0])
                ph.log('Expected to find the project file in the current directory')
                ph.log('with the name "%s".' % Backend.DefaultFilename)
                exit()
        else:
            if os.path.isfile(Backend.DefaultFilename):
                return Backend.DefaultFilename
            else:
                ph.usage()
                ph.log()
                ph.log('No project file could be found.')
                ph.log()
                ph.log('Specify it on the command line, e.g: %s project.ph' % sys.argv[0])
                ph.log('Expected to find the project file in the current directory')
                ph.log('with the name "%s".' % Backend.DefaultFilename)
                exit()

    def setOption(self, option, value):
        self.commandLineArguments['options'][unicode(option)] = unicode(value)

    def getOption(self, option, default = 'off'):
        ret = self.commandLineArguments['options'].get(unicode(option), unicode(default))
        if ret == 'off':
            ret = False
        elif ret == 'on':
            ret = True
        return ret


if __name__ == '__main__':
    _ph = ph()
