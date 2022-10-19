#!/usr/bin/env python3
#
# This script creates an archive with problems that can be imported
# into the problems folder in a mooshak contest. Run it with --help
# for usage information.
#
# WARNING: Importing an archive into a contest problems folder will
# erase any existing problems in the contest, so you should only do
# this before the contest starts.
#
# Copyright (c) 2022 Alexandre D. B. Jesus <https://adbjesus.com>
# 
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the “Software”), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software. 
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
import tarfile
import argparse
import logging
import tempfile
import string
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

def build_archive(problems=None, timeouts=1, archive="problems.tgz"):
    if problems is None:
        logging.info("Missing problem directories, using those in current path")
        problems = [p for p in Path(".").iterdir() if p.is_dir()]
    problems.sort()
    logging.info(f"Using problem directories: {', '.join(map(str, problems))}")

    if isinstance(timeouts, int):
        logging.info("timeouts is a single value, using as default for all problems")
        timeouts = [timeouts]*len(problems)
    elif isinstance(timeouts, list):
        for t in timeouts:
            if not isinstance(t, int):
                logging.critical("timeouts must be a list of ints")
                raise ValueError("timeouts must be a list of ints")
        if len(timeouts) != len(problems):
            if len(timeouts) == 1:
                logging.info("timeouts is a single value, using as default for all problems")
                timeouts = [timeouts[0]]*len(problems)
            else:
                logging.warning("len(timeouts) != len(problems), replicating last timeout")
                timeouts = timeouts + [timeouts[-1]]*(len(problems) - len(timeouts))
    else:
        logging.critical("timeouts must be an int or a list")
        raise ValueError("timeouts must be an int or a list")

    logging.info(f"Using timeouts: {', '.join(map(str, timeouts))}")

    archivefile = tarfile.open(archive, "w:gz")

    with tempfile.TemporaryDirectory() as tmpdir:
        logging.debug(f"Using temporary directory: {tmpdir}")

        xmlproblems = ET.Element("Problems")
        xmlproblems.set("Presents", "radio")
        for (p, t) in zip(map(Path, problems), timeouts):
            if not p.is_dir():
                logging.warning(f"Problem '{p}' is not a directory")
                logging.warning(f"Ignoring problem {p}")
                continue

            pname = p.name
            if pname not in string.ascii_uppercase:
                logging.warning(f"Directory name '{pname}' is not an ascii uppercase letter")
                logging.warning(f"Ignoring problem {p}")
                continue

            descriptionfile = p / "description.html"
            if not descriptionfile.is_file():
                logging.warning(f"Missing file '{descriptionfile}'")
                logging.warning(f"Ignoring problem {p}")
                continue

            testsdir = p / "tests"
            if not testsdir.is_dir():
                logging.warning(f"Missing tests directory '{testsdir}'")
                logging.warning(f"Ignoring problem {p}")
                continue

            inputs = sorted(list(testsdir.glob("*.in")))
            if len(inputs) == 0:
                logging.warning(f"Could not find inputs with '{testsdir}/*.in' pattern")
                logging.warning(f"Ignoring problem {p}")
                continue

            outputs = sorted(list(testsdir.glob("*.out")))
            if len(outputs) == 0:
                logging.warning(f"Could not find outputs with '{testsdir}/*.out' pattern")
                logging.warning(f"Ignoring problem {p}")
                continue

            inputsstems = list(map(lambda x: x.stem, inputs))
            outputsstems = list(map(lambda x: x.stem, outputs))
            if inputsstems != outputsstems:
                logging.warning(f"Inputs and outputs filenames do not match")
                logging.debug(f"inputs: {', '.join(inputsstems)}")
                logging.debug(f"outputs: {', '.join(outputsstems)}")
                logging.warning(f"Ignoring problem {p}")
                continue

            xmlproblem = ET.SubElement(xmlproblems, "Problem")
            xmlproblem.set("xml:id", pname)
            xmlproblem.set("Name", pname)
            xmlproblem.set("Title", pname)
            xmlproblem.set("Description", "description.html")
            xmlproblem.set("Timeout", str(t))

            problemdir = Path(tmpdir) / pname
            problemdir.mkdir(mode=0o755)
            shutil.copy(descriptionfile, problemdir / "description.html")
            testsdir = problemdir / "tests"
            testsdir.mkdir(mode=0o755)

            xmltests=ET.SubElement(xmlproblem, "Tests")
            xmltests.set("xml:id", f"{pname}.tests")
            for (inp, out, name) in zip(inputs, outputs, inputsstems):
                xmltest = ET.SubElement(xmltests, "Test")
                xmltest.set("xml:id", f"{pname}.tests.{name}")
                xmltest.set("input", inp.name)
                xmltest.set("output", out.name)
                testdir = testsdir / name
                testdir.mkdir(mode=0o755)
                shutil.copy(inp, testdir / inp.name)
                shutil.copy(out, testdir / out.name)

            archivefile.add(problemdir, arcname=pname)

        with open(Path(tmpdir) / "Content.xml", "wb") as xmlfile:
            logging.debug(f"Using xmlfile: {xmlfile}")
            xmlfile.write(ET.tostring(xmlproblems,
                                      encoding = "ISO-8859-1",
                                      xml_declaration=True))

        with open(Path(tmpdir) / "Content.xml", "r") as xmlfile:
            logging.debug("Content.xml contents BEGIN")
            for line in xmlfile.readlines():
                logging.debug(line.strip())
            logging.debug("Content.xml contents END")

        archivefile.add(Path(tmpdir) / "Content.xml", arcname="Content.xml")
        archivefile.close()

def main():
    parser = argparse.ArgumentParser(
        description="""
        Create an archive with problems to be imported to
        a mooshak contest problems folder.
        """
    )
    parser.add_argument("-p", metavar="DIR", nargs="+", type=Path,
                        help="""problem directories to include,
                        by default considers all directories in the current path""")
    parser.add_argument("-t", metavar="SEC", nargs="+", default=1, type=int,
                        help="""timeout in seconds for the problems,
                        if it is a single value use that for all problems,
                        otherwise should have the same size as the number of problems""")
    parser.add_argument("-a", metavar="NAME", type=Path, default=Path("problems.tar.gz"),
                        help="created archive name")

    logging_level = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR
    }
    parser.add_argument("-v", choices=logging_level.keys(), default="warning",
                        help="verbosity level, defaults to warning")

    args = parser.parse_args()

    logging.basicConfig(level=logging_level[args.v],
                        format="%(levelname)s: %(message)s")

    build_archive(problems=args.p, timeouts=args.t, archive=args.a)

if __name__ == '__main__':
    main()
