from lxml import etree
import codecs
import json
import collections
from ftplib import FTP
import re
from time import sleep
from tempfile import TemporaryFile
from zipfile import ZipFile, ZipInfo


class Zsource:

    ''' This class represents an interface to Zakupki's data source.
        Use to retrieve raw XML data applying arbitrary filters.
    '''

    def __init__(self):
        ''' init
        '''
        self.connection = FTP('ftp.zakupki.gov.ru', user='free', passwd='free')
        self.connection.cwd('fcs_regions')

    def refresh_list(self, region=''):
        ''' refresh_list
        '''
        self.files = []
        file_re = re.compile(r'^.*\.\w{,4}$')
        folders = []
        if region and region not in self.list_regions():
            print('Region {} not found, loading all regions'.format(region))
        current_folder = region
        while True:
            print(' ' * 100, end='\r')
            print(current_folder, len(self.files), sep='\t')
            nlst = self.connection.nlst(current_folder)
            folders.extend([x for x in nlst if not file_re.match(x) and x != current_folder])
            if len(folders) == 0:
                break
            current_folder = folders.pop(0)
            self.files.extend([x for x in nlst if file_re.match(x)])

    def list_regions(self):
        ''' list_regions
        '''
        return [x for x in self.connection.nlst() if not x.startswith('_')]

    def list_document_types(self):
        ''' list_document_types
        '''
        result = set()
        type_re = re.compile(r'.*/(\w+?)_[^/]+$')
        return set(type_re.match(f).group(1) for f in self.files)

    def retr_files(self, region=None, document_type=None):
        ''' retr_files
        '''
        files = self.files
        if region and region in self.list_regions():
            files = [f for f in files if f.startswith(region)]
        if document_type and document_type in self.list_document_types():
            files = [f for f in files if document_type in f]
        for path in files:
            for file in self.retr_file(path):
                yield file

    def retr_file(self, path, retry=3):
        ftp_size = self.connection.size(path)
        while retry > 0:
            tmp = TemporaryFile()
            self.connection.retrbinary('RETR {}'.format(path), tmp.write)
            down_size = tmp.tell()
            if down_size == ftp_size:
                break
            retry -= 1
        with ZipFile(tmp) as zf:
            for i in zf.infolist():
                yield zf.open(i)
        tmp.close()


def get_element_path(element):
    path = ''
    while element is not None:
        name = etree.QName(element).localname
        path = name + '.' + path
        element = element.getparent()
    return path


def get_element_dict(element):
    if len(element) == 0:  # leaf element
        return element.text if len(element.text) <= 512 else '...'
    # non-leaf
    name_counts = collections.Counter([etree.QName(child).localname for child in element.iterchildren()])
    result = {}
    for child in element.iterchildren():
        name = etree.QName(child).localname
        if name_counts[name] == 1:
            result[name] = get_element_dict(child)
        else:
            if name not in result:
                result[name] = []
            result[name].append(get_element_dict(child))
    return result


# with codecs.open('test.json', 'w', encoding='UTF-8') as output:
#     for event, element in xml:
#         json.dump(get_element_dict(element), output, ensure_ascii=False)
#         output.write('\n')
#         element.clear()
