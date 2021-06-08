#!/usr/bin/env python
#
# Ansible Playbook Run Utility
#

import getopt
import sys
import os
import stat
import subprocess
import json
import re
import fnmatch
import readline
import getpass
import ansible.constants as C

class ErrorExit(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

def myinput(prompt, prefill):
    def hook():
        readline.insert_text(prefill)
        readline.redisplay()
    readline.set_pre_input_hook(hook)
    result = input(prompt)
    readline.set_pre_input_hook()
    return result

class argset:

    def __init__(self):
        self.options = []
        self.remainder = []
        self.argname = []
        self.optdash = []
        self.longlist = []
        self.shortlist = ''
        self.extravars = {}
        self.extraname = []
        self.checkarg = False
        self.printarg = False
        self.debugarg = False
        self.savearg = False
        self.readarg = False
        self.listarg = False
        self.askarg = False
        self.quietarg = False
        self.vaultarg = False
        self.hostarg = False
        self.factarg = False
        self.cryptfilearg = False
        self.passvararg = False
        self.saveFileKey = None
        self.readFileKey = None
        self.factSearchKey = None
        self.cryptFileName = None
        self.passVarName = None
        self.addArg("c", "check", True)
        self.addArg("p", "print", True)
        self.addArg("d", "debug", True)
        self.addArg("l", "list", True)
        self.addArg("?", "help", True)
        self.addArg("a", "ask", True)
        self.addArg("q", "quiet", True)
        self.addArg("v", "vault", True)
        self.addArg("s", "save", False)
        self.addArg("r", "read", False)
        self.addArg("h", "host", False)
        self.addArg("f", "fact", False)
        self.addArg("e", "cryptfile", False)
        self.addArg("P", "passvar", False)
        self.playSaveContents = {}
        self.playReadFile = None
        self.saveFileVersion = 4
        self.playBasename = None

        if os.getenv('helper_data_directory'):
            self.playSaveDir = os.getenv('helper_data_directory')
        else:
            self.playSaveDir = os.path.expanduser("~") + "/.ansible-helper"

        try:
            self.playbook = sys.argv[1]
            sys.argv.pop(1)
            self.playBasename = os.path.basename(self.playbook)
        except IndexError as e:
            print("Playbook should be first argument. Can not open playbook: %s" % str(e))
            sys.exit(1)

        try:
            nextArg = sys.argv[1]
            if nextArg == "-r":
                self.readFileKey = sys.argv[2]
                self.readarg = True
        except Exception:
            pass

    def print_help(self, *args):
        if args:
            for errText in args:
                print("[!] Error: " + errText)
            sys.exit(1)
        else:
            print("Usage: " + sys.argv[0] + " playbook.yaml [ -p | -l | -s save_key | -r save_key ] | [ -c | -d ] --extra_var1 value --extra_var2 value ...")
            sys.exit(1)

    def addArg(self, shortarg, longarg, isFlag):

        self.argname.append(longarg)
        optdash = '--' + longarg
        self.optdash.append(optdash)
        if isFlag:
            self.longlist.append(longarg)
        else:
            longarg = longarg + "="
            self.longlist.append(longarg)
        if shortarg:
            if isFlag:
                self.shortlist = self.shortlist + shortarg
            else:
                self.shortlist = self.shortlist + shortarg + ":"

    def parseArgs(self):

        try:
            self.options, self.remainder = getopt.getopt(sys.argv[1:], self.shortlist, self.longlist)
        except getopt.GetoptError as e:
            print("Can not parse arguments: %s" % str(e))
            self.print_help()

        for opt, arg in self.options:
            if opt in ('-?', '--help'):
                self.print_help()
            elif opt in ('-c', '--check'):
                self.checkarg = True
            elif opt in ('-d', '--debug'):
                self.debugarg = True
            elif opt in ('-a', '--ask'):
                self.askarg = True
            elif opt in ('-q', '--quiet'):
                self.quietarg = True
            elif opt in ('-v', '--vault'):
                self.vaultarg = True
            elif opt in ('-h', '--host'):
                self.hostarg = True
                self.runHostName = arg
            elif opt in ('-f', '--fact'):
                self.factarg = True
                self.factSearchKey = arg
            elif opt in ('-e', '--cryptfile'):
                self.cryptfilearg = True
                self.vaultarg = True
                self.cryptFileName = arg
            elif opt in ('-P', '--passvar'):
                self.passvararg = True
                self.vaultarg = True
                self.passVarName = arg
            elif opt in ('-p', '--print'):
                if len(self.options) != 1:
                    print("Print option can not be combined with other options.")
                    sys.exit(1)
                self.printarg = True
                self.printArgs()
            elif opt in ('-l', '--list'):
                if len(self.options) != 1:
                    print("List option can not be combined with other options.")
                    sys.exit(1)
                self.listarg = True
            elif opt in ('-s', '--save'):
                if len(self.options) != 1:
                    print("Save option can not be combined with other options.")
                    sys.exit(1)
                if re.findall('[^a-zA-Z0-9-_]', arg):
                    print("Save key should not contain special characters.")
                    sys.exit(1)
                self.savearg = True
                self.saveFileKey = arg
            elif opt in ('-r', '--read'):
                self.readarg = True
                self.saveFileKey = arg
            elif opt in self.optdash:
                optname = opt.strip('--')
                argstring = arg.replace('\\', '\\\\')
                extravaritem = '"' + optname + '":"' + argstring + '"'
                self.extravars[optname] = extravaritem

    def parsePlaybook(self):
        try:
            with open(self.playbook, 'r') as yamlfile:
                for line in yamlfile:
                    if line.startswith('#'):
                        if 'var:' in line:
                            varline = line.split(':')
                            if (len(varline) > 1):
                                variable = varline[1].rstrip("\n")
                                self.addArg(None, variable, False)
                                self.extraname.append(variable)
                        if 'option:' in line:
                            optline = line.split(':')
                            if (len(optline) > 1):
                                option = optline[1].rstrip("\n")
                                if option == 'quiet':
                                    self.quietarg = True
                                elif option == 'dense':
                                    os.environ['ANSIBLE_STDOUT_CALLBACK'] = 'community.general.dense'
                                elif option == 'selective':
                                    os.environ['ANSIBLE_STDOUT_CALLBACK'] = 'selective'
                                else:
                                    print("Unsupported option: %s" % option)
                                    sys.exit(1)
        except OSError as e:
            print("Can not open playbook: %s" % str(e))
            sys.exit(1)

    def printArgs(self):
            for x in range(len(self.optdash)):
                print (self.optdash[x])
            sys.exit(0)

    def storeSavedPlay(self):
        if self.readarg:
            self.playReadFile = self.playSaveDir + "/" + self.readFileKey + ".json"
            if os.path.exists(self.playReadFile):
                try:
                    with open(self.playReadFile, 'r') as saveFile:
                        try:
                            saveData = json.load(saveFile)
                        except ValueError as e:
                            print("Save file does not contain valid JSON data: %s" % str(e))
                            sys.exit(1)
                        saveFileIter = iter(saveData)
                        for key in saveData:
                            if key == 'saveFileVersion':
                                if saveData[key] != self.saveFileVersion:
                                    print("Save file version error, file version %s required version %s" % (saveData[key], self.saveFileVersion))
                                    sys.exit(1)
                                continue
                            if key == 'playbookBaseName':
                                if saveData[key] != self.playBasename:
                                    print("Playbook name mismatch, got %s expecting %s" % (saveData[key], self.playBasename))
                                    sys.exit(1)
                                continue
                            self.playSaveContents[key] = saveData[key]
                    saveFile.close()
                except OSError as e:
                    print("Could not read save file: %s" % str(e))
                    sys.exit(1)

                for key in self.playSaveContents['options']:
                    saveParamvalue = self.playSaveContents['options'][key]
                    extravaritem = '"' + key + '":"' + saveParamvalue + '"'
                    self.extravars[key] = extravaritem

class playrun:

    def __init__(self, argclass):

        self.runargs = argclass
        self.playDirname = os.path.dirname(self.runargs.playbook)
        if not self.playDirname:
            self.playDirname = '.'
        self.playBasename = self.runargs.playBasename
        self.playName = os.path.splitext(self.playBasename)[0]
        self.playSaveDir = self.runargs.playSaveDir
        self.vaultPasswordFile = None
        self.playSaveFile = None

        if not os.path.exists(self.playSaveDir):
            try:
                os.makedirs(self.playSaveDir, mode=0o770)
            except OSError as e:
                print("Can not make directory: %s" % str(e))
                sys.exit(1)

        if os.getenv('ANSIBLE_CONFIG'):
            self.ansibleConfig = os.getenv('ANSIBLE_CONFIG')
        elif os.path.exists("ansible.cfg"):
            self.ansibleConfig = "ansible.cfg"
        elif os.path.exists("~/.ansible.cfg"):
            self.ansibleConfig = "~/.ansible.cfg"
        elif os.path.exists("/etc/ansible/ansible.cfg"):
            self.ansibleConfig = "/etc/ansible/ansible.cfg"
        else:
            self.ansibleConfig = None

        if self.ansibleConfig:
            try:
                with open(self.ansibleConfig, 'r') as configFile:
                    while True:
                       line = configFile.readline()
                       line = line.replace(" ", "")
                       line = line.rstrip("\n")
                       if not line:
                           break
                       if not line.startswith("#"):
                           try:
                               key,value = line.split("=")
                               if key == "vault_password_file":
                                   if os.path.exists(value):
                                       self.vaultPasswordFile = value
                           except ValueError:
                               continue
                    configFile.close()
            except OSError as e:
                print("Could not read ansible config file: %s" % str(e))
                sys.exit(1)

    def listSavedPlays(self):
        if os.path.exists(self.playSaveDir):
            count = 1
            for fileName in os.listdir(self.playSaveDir):
                listFile = self.playSaveDir + "/" + fileName
                if os.path.isfile(listFile):
                    try:
                        with open(listFile, 'r') as saveFile:
                            try:
                                saveData = json.load(saveFile)
                            except ValueError as e:
                                print("Warning: skipping %s: file does not contain JSON data" % fileName)
                                continue

                        for key in saveData:
                            if key == 'playbookBaseName':
                                if saveData[key] == self.playBasename:
                                    print("%d) %s" % (count, os.path.splitext(fileName)[0]))
                                    count = count + 1

                    except OSError as e:
                        print("Could not read file: %s" % str(e))
                        sys.exit(1)

    def savePlay(self):

        if not self.runargs.saveFileKey:
            raise ErrorExit("savePlay: Error: saveFileKey not defined")

        self.playSaveFile = self.playSaveDir + "/" + self.runargs.saveFileKey + ".json"

        try:
            saveData = {"saveFileVersion" : self.runargs.saveFileVersion, "playbookBaseName" : self.playBasename}
            saveData['options'] = {}

            with open(self.playSaveFile, 'w') as saveFile:
                for x in range(len(self.runargs.extraname)):
                    inputOptText = input(self.runargs.extraname[x] + ": ")
                    inputOptText = inputOptText.rstrip("\n")
                    if inputOptText != '':
                        paramBlock = { self.runargs.extraname[x] : inputOptText }
                        saveData['options'].update(paramBlock)
                json.dump(saveData, saveFile, indent=4)
                saveFile.write("\n")
                saveFile.close()
        except OSError as e:
            print("Could not write save file: %s" % str(e))
            sys.exit(1)

    def runPlay(self):

        cmdlist = []
        runcmd = ''
        extravarjson = ''

        if self.runargs.quietarg:
            os.environ['ANSIBLE_STDOUT_CALLBACK'] = 'minimal'

        if self.runargs.askarg:
            try:
                inputPassword = getpass.getpass()
                checkPassword = getpass.getpass(prompt='Confirm password: ')
            except Exception as e:
                print("Can not read password input: %s" % str(e))
            else:
                if inputPassword != checkPassword:
                    print("Passwords do not match")
                    sys.exit(1)
                extravaritem = '"ask_password":"' + inputPassword + '"'
                self.runargs.extravars['ask_password'] = extravaritem

        if self.runargs.passvararg:
            extravaritem = '"password_var":"' + self.runargs.passVarName + '"'
            self.runargs.extravars['password_var'] = extravaritem

        if self.runargs.extravars:
            optCount = len(self.runargs.extravars)
            count = 1
            extravarjson = '\'{'
            for key in self.runargs.extravars:
                if count == optCount:
                    extravarjson = extravarjson + self.runargs.extravars[key] + '}\''
                else:
                    extravarjson = extravarjson + self.runargs.extravars[key] + ','
                    count = count + 1

            extravarexec = '--extra-vars ' + extravarjson
        else:
            extravarexec = ''

        cmdlist.append("ansible-playbook")
        if self.runargs.hostarg:
            cmdlist.append('-i')
            cmdlist.append(self.runargs.runHostName + ',')
        cmdlist.append(self.runargs.playbook)
        if not self.vaultPasswordFile and self.runargs.vaultarg:
            cmdlist.append('--ask-vault-pass')
        cmdlist.append(extravarexec)
        if self.runargs.checkarg:
            cmdlist.append('--check')
        if self.runargs.debugarg:
            cmdlist.append('-vvv')
        if self.runargs.cryptfilearg:
            cmdlist.append('-e')
            cmdlist.append('@' + self.runargs.cryptFileName)

        for x in range(len(cmdlist)):
            if (x == 0):
                runcmd = cmdlist[x]
            else:
                runcmd = runcmd + ' ' + cmdlist[x]

        if not self.runargs.askarg and self.runargs.debugarg:
            print (runcmd)

        if self.runargs.factarg:
            os.environ['ANSIBLE_STDOUT_CALLBACK'] = 'ansible.posix.json'
            ansible_output = subprocess.check_output(runcmd, shell=True)
            ansible_output_json = json.loads(ansible_output)
            for x in range(len(ansible_output_json['plays'])):
                for y in range(len(ansible_output_json['plays'][x]['tasks'])):
                    for task_host in ansible_output_json['plays'][x]['tasks'][y]['hosts']:
                        for key in ansible_output_json['plays'][x]['tasks'][y]['hosts'][task_host]:
                            if key == 'ansible_facts':
                                if self.runargs.factSearchKey in ansible_output_json['plays'][x]['tasks'][y]['hosts'][task_host][key]:
                                    print(ansible_output_json['plays'][x]['tasks'][y]['hosts'][task_host][key][self.runargs.factSearchKey])
        else:
            os.system(runcmd)

def main():

    os.environ['ANSIBLE_HOST_KEY_CHECKING'] = 'False'
    os.environ['ANSIBLE_LOCALHOST_WARNING'] = 'False'
    os.environ['ANSIBLE_ACTION_WARNINGS'] = 'False'
    os.environ['ANSIBLE_COMMAND_WARNINGS'] = 'False'
    os.environ['ANSIBLE_DEPRECATION_WARNINGS'] = 'False'
    os.environ['ANSIBLE_DISPLAY_SKIPPED_HOSTS'] = 'False'

    runArgs = argset()
    runArgs.parsePlaybook()
    runArgs.storeSavedPlay()
    runArgs.parseArgs()

    playRun = playrun(runArgs)
    if runArgs.listarg:
        playRun.listSavedPlays()
    elif runArgs.savearg:
        playRun.savePlay()
    else:
        playRun.runPlay()

if __name__ == '__main__':

    try:
        main()
    except SystemExit as e:
        if e.code == 0:
            os._exit(0)
        else:
            os._exit(e.code)
