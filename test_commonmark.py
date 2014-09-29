
from __future__ import print_function

import traceback
import re
import os
import sys
import argparse
from pprint import pprint, pformat

import commonmark


def print_exc_plus():
    """
    Print the usual traceback information, followed by a listing of all the
    local variables in each frame.
    """
    msg = []
    tb = sys.exc_info()[2]
    while 1:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    stack.append(f)
#     while f:
#         stack.append(f)
#         f = f.f_back
    stack.reverse()
    msg.append(traceback.format_exc())
    msg.append("Locals by frame, innermost last")
    for frame in stack:
        msg.append('')
        msg.append("Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno))
        for key, value in frame.f_locals.items():
            # We have to be careful not to cause a new error in our error
            # printer! Calling str() on an unknown object could cause an
            # error we don't want.
            try:
                msg.append("\t%20s = %r" % (key, value))
            except:
                msg.append("{} = <ERROR WHILE PRINTING VALUE>".format(key))

    return '\n'.join(msg)



def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--stop', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-t', '--test', type=int, default=None)
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
    test_number = 1
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
        number = test['number']
        if args.test is not None and number != args.test:
            continue

        section = test['section']
        if section != current_section:
            print('SECTION: {0}'.format(section))
            current_section = section

        markdown = test['markdown']
        html = test['html']
        try:
            actual = writer.render_block(reader.parse(markdown))
        except Exception:
            actual = None
            tmsg = print_exc_plus()
            tmsg = tmsg.encode('ascii', errors='replace')
        else:
            tmsg = None

        if actual == html:
            passed += 1
            print('TEST {0} of {1}: PASS'.format(number, cnt))
        else:
            failed += 1
            print('TEST {0} of {1}: FAIL'.format(number, cnt))
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

                with open(r'C:\temp\commonmark_actual.txt', 'w') as f:
                    f.write(actual.encode('utf8'))
                with open(r'C:\temp\commonmark_html.txt', 'w') as f:
                    f.write(html.encode('utf8'))

            if args.stop:
                print('DUMP')
                pprint(reader.dump())
                return None

    print('PASSED: {}'.format(passed))
    print('FAILED: {}'.format(failed))






if __name__ == '__main__':
    main()



