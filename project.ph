ProjectName('Project Helper, a Cython project build system')

ProjectVersion('1.0.0')

ProjectDescription('''
Project Helper is a Cython project build system. It's like distutils/cmake,
only specifically made for Cython projects. It aims to support a fully
featured build system on major platforms, e.g. Windows, Linux, and Mac.
In addition to supporting major platforms, it supports multiple compilers:
 (Linux) gcc
 (Windows) Microsoft Visual C
 (Mac) gcc
''')

ProjectLink('cython-ph.googlecode.com')
ProjectOptions({
    'build': 'Compile ph.py into an single executable named just "ph".',
    'clean': 'Clean up the directories contents.',
})


#- Run will be called when ph is ready for your project to do things
def run():
    if GetOption('build'):
        log('Building ph executable')
        cython('ph.py', 'ph', embed = True)
        if GetOption('build-extras'):
            log('You requested that we build extras, but that is just silly.')
        dispatch() #- Flush the commands (cython, compiler commands, etc)

    if GetOption('clean'):
        log('Cleaning up .c and .pyx files')
        #delete('ph' + PlatformBinaryExtension()) #- .exe in the event of windows
        # We will keep the above binary, instead
        delete('ph.c')

