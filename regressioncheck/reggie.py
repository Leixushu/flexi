import argparse
import numpy as np
import os
import logging
import tools
import check
from timeit import default_timer as timer
#import ast
#import re
                                
start = timer()
global_run_number=0
global_errors=0
build_number=0

parser = argparse.ArgumentParser(description='Regression checker for NRG codes.', formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-c', '--carryon', action='store_true', help='''Continue build/run process. 
  --carryon         : build non-existing binary-combinations and run all examples for thoses builds
  --carryon --run   : run all failed examples''')
parser.add_argument('-e', '--exe', help='Path to executable of code that should be tested.')
parser.add_argument('-d', '--debug', type=int, default=0, help='Debug level.')
parser.add_argument('-j', '--buildprocs', type=int, default=0, help='Number of processors used for compiling (make -j XXX).')
parser.add_argument('-b', '--basedir', help='Path to basedir of code that should be tested (contains CMakeLists.txt).')
parser.add_argument('-y', '--dummy', action='store_true',help='use dummy_basedir and dummy_checks for fast testing on dummy code')
parser.add_argument('-r', '--run', action='store_true' ,help='run all binaries for all examples with all run-combinations for all existing binaries')
parser.add_argument('check', help='Path to check-/example-directory.')

args = parser.parse_args() # reggie command line arguments

print('='*132)
print "reggie2.0, add nice ASCII art here"
print('='*132)
cwd = os.getcwd()                                          # start with current working directory
found = os.path.exists(os.path.join(cwd,args.check)) # check if directory exists
if not found :
    print "Check directory not found: ",os.path.join(cwd,args.check)
    exit(1)

# setup logger for printing information, debug messages to stdout
tools.setup_logger(args.debug)
log = logging.getLogger('logger')

# setup basedir (search upward from staring point of reggie)
if args.dummy : # 
    args.check = 'dummy_checks/test'
    print "Check directoryswitched to ",args.check
    args.basedir = os.path.abspath('dummy_basedir')
    #print "basedir = ".ljust(25)+basedir
else :
    try :
        args.basedir = tools.find_basedir()
        #print "basedir = [".ljust(15)+basedir,"]"
    except Exception,ex :
        args.basedir = os.path.abspath('dummy_basedir')

# delete the building directory when [carryon = False] and [run = False] before getBuilds is called
if not args.carryon and not args.run : tools.clean_folder("reggie_outdir")

# get builds from checks directory if no executable is supplied
if args.exe is None : # if not exe is supplied, get builds
    # read build combinations from checks/XX/builds.ini
    builds = check.getBuilds(args.basedir, args.check)
else :
    found = os.path.exists(args.exe) # check if executable exists
    if not found :
        print tools.red("no executable found under ")
        exit(1)
    else :
        builds = [check.Standalone(args.exe,args.check)] # set builds list to contain only the supplied executable
        args.run = True
        args.basedir = None


if args.run :
    print "args.run -> skip building"
    # remove all build from builds when build.binary_exists() = False
    print builds[0].binary_exists()
    builds = [build for build in builds if build.binary_exists()]



# display all command line arguments
print "Running with the following command line options"
for arg in args.__dict__ :
    print arg.ljust(15)," = [",getattr(args,arg),"]"
print('='*132)




# General worflow:
# 1.   loop over alls builds
# 1.1    compile the build if args.run is false and the binary is non-existent
# 1.1    read the example directories
# 2.   loop over all example directories
# 2.1    read the command line options for binary execution (e.g. number of threads for mpirun) 
# 2.2    read the analyze options within each example directory

# compile and run loop
try : # if compiling fails -> go to exception
    for build in builds :
        build_number+=1 # count number of builds
        print "Build Cmake Configuration ",build_number," of ",len(builds)," ...",
        log.info(str(build))
        build.compile(args.buildprocs)
        if not args.carryon :
            tools.clean_folder(os.path.join(build.target_directory,"examples"))
        # get example folders: run_basic/example1, run_basic/example2 from check folder
        build.examples = check.getExamples(args.check, build)
        for example in build.examples :
            log.info(str(example))
            # get command line options: MPI=1,2,3 from 'command_line.ini'
            example.command_lines = \
                    check.getCommand_Lines(os.path.join(example.source_directory,'command_line.ini'), example)
            # get analyze parameters: L2, convtest, line integral from 'analyze.ini'
            example.analyzes = \
                    check.getAnalyzes(os.path.join(example.source_directory,'analyze.ini'), example)
            for command_line in example.command_lines :
                log.info(str(command_line))
                # get setup parameters: N=, mesh=, etc. from 'parameter.ini'
                command_line.runs = \
                        check.getRuns(os.path.join(example.source_directory,'parameter.ini' ), command_line)
                for run in command_line.runs :
                    log.info(str(run))
                    run.execute(build,command_line)
                    global_run_number+=1
                    run.globalnumber=global_run_number
                    if not run.successful :
                        global_errors+=1

                print tools.blue(">>>>>>>>>>>>>> ANALYZE <<<<<<<<<<<<<<<")
                runs_successful = [run for run in command_line.runs if run.successful]
                for analyze in example.analyzes :
                    print tools.blue(str(analyze.options))
                    analyze.perform(runs_successful)

                print tools.blue(">>>>>>>>>>>>>> RENAME <<<<<<<<<<<<<<<")
                for run in runs_successful : # all successful runs
                    if not run.analyze_successful : # if analyze fails: rename
                        print run.target_directory
                        run.rename_failed()

                #    # h-Convergence test





        print('='*132)
except check.BuildFailedException,ex:
    print tools.bcolors.WARNING+""
    print ex # display error msg
    print tools.indent(" ".join(build.cmake_cmd),1)
    print tools.indent(" ".join(ex.build.make_cmd),1)
    print tools.indent("Build failed, see: "+ex.build.stdout_filename,1)
    print tools.indent("                   "+ex.build.stderr_filename,1)+tools.bcolors.ENDC
    print tools.bcolors.FAIL
    for line in ex.build.stderr[-20:] :
        print tools.indent(line,4),
    print tools.bcolors.ENDC
    tools.finalize(start,"FAILED!")
    exit(1)









print('='*132)
param_str_old=""
print " Summary of Errors"+"\n"
d = ' '
d2 = '.'
#invalid_keys = {"MPI", "binary", "analyze*"} # define keys to be removed from a dict
#parameters_removed = tools.without_keys(command_line.parameters, invalid_keys) # remove keys from dict

print "#run".center(8,d),"options".center(37,d2),"path".center(44,d),"MPI".center(9,d2),"runtime".rjust(10,d),"Information".rjust(15,d2)
for build in builds :
    #print('-'*132)
    print " "
    if type(build) is check.Build : print " ".join(build.cmake_cmd)
    for example in build.examples :
        for command_line in example.command_lines :
            #line=", ".join(["%s=%s"%item for item in command_line.parameters.items()])
            #print tools.yellow(tools.indent(line,4," "))
            for run in command_line.runs :
                #if run.target_directory_exists :
                    #continue
                line=", ".join(["%s=%s"%item for item in run.parameters.items()[1:]]) # skip first index
                if line != param_str_old : # only print when the parameter set changes
                    print tools.yellow(tools.indent(line,5))
                param_str_old=line
                line=str(run.globalnumber).center(9,d)+" "*3 # global run number

                line+= tools.yellow("%s=%s"%(run.parameters.items()[0])) # only use first index
                line=line.ljust(55,d) # inner most run variable (e.g. TimeDiscMethod)

                # build/example/reggie/run info
                line+=os.path.relpath(run.target_directory,"reggie_outdir").ljust(25,d2)

                line+=command_line.parameters.get('MPI','-').center(9,d)
                line+="%2.2f".rjust(12,d2) % (run.execution_time)
                line+=run.result.rjust(25,d) # add result (successful or failed)
                print line
                for result in run.analyze_results :
                    print tools.red(result).rjust(137)
        print ""

if global_errors > 0 :
    tools.finalize(start,"Failed! Number of errors: "+str(global_errors))
else :
    tools.finalize(start,"successful")



