#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Import standard python libraries
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time
import rdflib

# Import schema.org libraries
if not os.getcwd() in sys.path:
    sys.path.insert(1, os.getcwd())

import software
import software.util.buildocspages as buildocspages
import software.util.buildtermpages as buildtermpages
import software.util.copystaticdocsplusinsert as copystaticdocsplusinsert
import software.util.fileutils as fileutils
import software.util.runtests as runtests_lib
import software.util.schemaglobals as schemaglobals
import software.util.schemaversion as schemaversion
import software.util.textutils as textutils

from sdotermsource import SdoTermSource
from sdocollaborators import collaborator
from sdoterm import *
from schemaexamples import SchemaExamples
from localmarkdown import Markdown

parser = argparse.ArgumentParser()
parser.add_argument('-a','--autobuild', default=False, action='store_true', help='clear output directory and build all components - overrides all other settings (except -examplesnum)')
parser.add_argument('-c','--clearfirst', default=False, action='store_true', help='clear output directory before creating contents')
parser.add_argument('-d','--docspages', default=[],action='append',nargs='*', help='create docs page(repeatable) - ALL = all pages')
parser.add_argument('-e','--examplesnum', default=False, action='store_true', help='Add missing example ids')
parser.add_argument('-f','--files', default=[], action='append', nargs='*', help='create files(repeatable) - ALL = all files')
parser.add_argument('-o','--output', help='output site directory (default: ./software/site)')
parser.add_argument('-r','--runtests', default=False, action='store_true', help='run test scripts before creating contents')
parser.add_argument('-s','--static', default=False, action='store_true', help='Refresh static docs in site image')
parser.add_argument('-t','--terms', default=[], action='append', nargs='*', help='create page for term (repeatable) - ALL = all terms')
parser.add_argument('-b','--buildoption',default= [],action='append', nargs='*', help='build option(repeatable) - flags to be passed to build code')
parser.add_argument('--rubytests', default=False, action='store_true', help='run the post generation ruby tests')
parser.add_argument('--release', default=False, action='store_true', help='create page for term (repeatable) - ALL = all terms')
args = parser.parse_args()


for op in args.buildoption:
    schemaglobals-BUILDOPTS.extend(op)


for ter in args.terms:
    schemaglobals.TERMS.extend(ter)

for pgs in args.docspages:
    schemaglobals.PAGES.extend(pgs)

for fls in args.files:
    schemaglobals.FILES.extend(fls)

if args.output:
    schemaglobals.OUTPUTDIR = args.output

if args.autobuild or args.release:
    schemaglobals.TERMS = ['ALL']
    schemaglobals.PAGES = ['ALL']
    schemaglobals.FILES = ['ALL']


def clear():
    if args.clearfirst or args.autobuild:
        print('Clearing %s directory' % schemaglobals.OUTPUTDIR)
        if os.path.isdir(schemaglobals.OUTPUTDIR):
            for root, dirs, files in os.walk(schemaglobals.OUTPUTDIR):
                for f in files:
                    if f != '.gitkeep':
                        os.unlink(os.path.join(root, f))
                for d in dirs:
                    shutil.rmtree(os.path.join(root, d))

###################################################
#RUN TESTS
###################################################
def runtests():
    if args.runtests or args.autobuild:
        print('Running test scripts before proceeding...\n')
        errorcount = runtests_lib.main('./software/tests/')
        if errorcount:
            print('Errors returned: %d' % errorcount)
            sys.exit(errorcount)
        else:
            print('Tests successful!\n')


###################################################
#INITIALISE Directory
###################################################

def initdir(output_dir, handler_path):
    print('Building site in "%s" directory' % output_dir)
    fileutils.createMissingDir(output_dir)
    clear()
    fileutils.createMissingDir(os.path.join(output_dir, 'docs'))
    fileutils.createMissingDir(os.path.join(output_dir, 'docs/contributors'))
    fileutils.createMissingDir(os.path.join(output_dir, 'empty')) #For apppengine 404 handler
    fileutils.createMissingDir(os.path.join(output_dir, 'releases', schemaversion.getVersion()))

    gdir = os.path.join(output_dir, 'gcloud')
    fileutils.createMissingDir(gdir)

    print('\nCopying docs static files')
    copystaticdocsplusinsert.copyFiles('./docs', './software/site/docs', indent='▶ ')
    print('Done')

    print('\nPreparing GCloud files')
    gcloud_files = glob.glob('software/gcloud/*.yaml')
    for path in gcloud_files:
      shutil.copy(path, gdir)
    print('Done: copied %d files' % len(gcloud_files))
    print('\nCreating %s from %s for version: %s' %
        (handler_path, schemaglobals.HANDLER_TEMPLATE, schemaversion.getVersion()))
    with open(os.path.join(gdir, schemaglobals.HANDLER_TEMPLATE)) as template_file:
      template_data = template_file.read()
      with open(os.path.join(gdir, handler_path), mode='w') as yaml_file:
        handler_data = template_data.replace('{{ver}}', schemaversion.getVersion())
        yaml_file.write(handler_data)
    print('Done\n')


###################################################
#MARKDOWN INITIALISE
###################################################
Markdown.setWikilinkCssClass('localLink')
Markdown.setWikilinkPrePath('/')
Markdown.setWikilinkPostPath('')

###################################################
#TERMS SOURCE LOAD
###################################################
LOADEDTERMS = False
def loadTerms():
    global LOADEDTERMS
    if not LOADEDTERMS:
        LOADEDTERMS = True
        if not SdoTermSource.SOURCEGRAPH:
            print('Loading triples files')
            SdoTermSource.loadSourceGraph('default')
            print ('loaded %s triples - %s terms' % (len(SdoTermSource.sourceGraph()),len(SdoTermSource.getAllTerms())) )
            collaborator.loadContributors()


###################################################
#EXAMPLES SOURCE LOAD
###################################################
LOADEDEXAMPLES = False
def loadExamples():
    global LOADEDEXAMPLES
    if not LOADEDEXAMPLES:
        SchemaExamples.loadExamplesFiles('default')
        print('Loaded %d examples ' % (SchemaExamples.count()))


###################################################
#BUILD INDIVIDUAL TERM PAGES
###################################################
def processTerms(terms):
    import buildtermpages
    if len(terms):
        print('Building term definition pages\n')
        loadTerms()
        loadExamples()
    buildtermpages.buildTerms(terms)

###################################################
#BUILD DYNAMIC DOCS PAGES
###################################################
def processDocs(pages):
    import buildocspages
    if len(pages):
        print('Building dynamic documentation pages\n')
        loadTerms()
        buildocspages.buildDocs(pages)

###################################################
#BUILD FILES
###################################################
def processFiles(files):
    import buildfiles
    if len(files):
        print('Building supporting files\n')
        loadTerms()
        loadExamples()
        buildfiles.buildFiles(files)

###################################################
#Run ruby tests
###################################################

def runRubyTests(release_dir):
    print('Setting up LATEST')
    version = schemaversion.getVersion()
    src_dir = os.path.join(os.getcwd(), release_dir, version)
    dst_dir = os.path.join(os.getcwd(), release_dir, 'LATEST')
    os.symlink(src_dir, dst_dir)
    cmd = ['bundle', 'exec', 'rake']
    cwd = os.path.join(os.getcwd(), 'software/scripts')
    print('Running tests')
    subprocess.check_call(cmd, cwd=cwd)
    print('Cleaning up %s' % dst_dir)
    os.unlink(dst_dir)
    print('Done')

###################################################
#COPY CREATED RELEASE FILES into Data area
###################################################


def copyReleaseFiles(release_dir):
    version = schemaversion.getVersion()
    print('Copying release files for version %s to data/releases' % version)
    srcdir = os.path.join(os.getcwd(), release_dir, version)
    destdir = os.path.join(os.getcwd(), 'data/releases/', version)
    fileutils.mycopytree(srcdir, destdir)
    cmd = ['git', 'add', destdir]
    subprocess.check_call(cmd)


###################################################
# Main program
###################################################

if __name__ == '__main__':
    software.CheckWorkingDirectory()
    print('Version: %s  Released: %s' % (schemaversion.getVersion(), schemaversion.getCurrentVersionDate()))
    if args.release:
        args.autobuild = True
        print('BUILDING RELEASE VERSION')
        time.sleep(2)
        print()
    if args.examplesnum or args.release or args.autobuild:
        print('Checking Examples for assigned identifiers')
        time.sleep(2)
        print()
        cmd = ['./software/SchemaExamples/utils/assign-example-ids.py']
        subprocess.check_call(cmd)
        print()
    initdir(output_dir=schemaglobals.OUTPUTDIR, handler_path=schemaglobals.HANDLER_FILE)
    runtests()
    processTerms(terms=schemaglobals.TERMS)
    processDocs(pages=schemaglobals.PAGES)
    processFiles(files=schemaglobals.FILES)
    if args.rubytests:
        runRubyTests(release_dir=schemaglobals.RELEASE_DIR)
    if args.release:
        copyReleaseFiles(release_dir=schemaglobals.RELEASE_DIR)


