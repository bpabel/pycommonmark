
from __future__ import print_function

import traceback
import re
import os
import sys
import argparse
from pprint import pprint, pformat

import commonmark


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--stop', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    writer = commonmark.HtmlRenderer()
    reader = commonmark.DocParser()


    print('Reading spec...')
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spec.txt')
    with open(fp, 'rU') as f:
        text = f.read()

    text = text.decode('utf8')
    text = text.replace(u'\u2192', '\t')
    text = re.sub(r'^<!-- END TESTS -->(.|[\n])*', '', text, flags=re.M)


    print('Parsing tests...')
    regex = re.compile(r'^\.\n(?P<markdown>[\s\S]*?)^\.\n(?P<html>[\s\S]*?)^\.$|^#{1,6} *(?P<section>.*)$', flags=re.M)

    tests = []
    test_number = 0
    current_section = None
    for match in regex.finditer(text):
        if match.group('section'):
            current_section = match.group('section')
            # print('Found Section: {}'.format(current_section))

        else:
            test = {
                'section': current_section,
                'markdown': match.group('markdown'),
                'html': match.group('html'),
                'number': test_number,
            }
            # print('Found Test: {}'.format(test_number))
            test_number += 1
            tests.append(test)


    passed = 0
    failed = 0
    print('Running Tests...')
    cnt = len(tests)
    current_section = None
    for test in tests:
        section = test['section']
        if section != current_section:
            print('SECTION: {0}'.format(section))
            current_section = section

        markdown = test['markdown']
        html = test['html']
        try:
            actual = writer.renderBlock(reader.parse(markdown))
        except Exception:
            actual = None
            tmsg = traceback.format_exc()
        else:
            tmsg = None

        if actual == html:
            passed += 1
            print('{0} of {1}: PASS'.format(test['number'] + 1, cnt))
        else:
            failed += 1
            print('{0} of {1}: FAIL'.format(test['number'] + 1, cnt))
            if args.verbose:
                print('.')
                print(markdown.encode('ascii', errors='replace'))
                print('.')
                print(html.encode('ascii', errors='replace'))
                print('.')
                print(actual.encode('ascii', errors='replace') if actual else actual)
                print('.')
                if tmsg:
                    print(tmsg)

            if args.stop:
                pprint(reader.dump())
                return None

    print('PASSED: {}'.format(passed))
    print('FAILED: {}'.format(failed))






if __name__ == '__main__':
    main()



