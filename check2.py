#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
General check module[v2] +
Check object: str num list file +
@reference: Lihuan
@author: WangMing
Maintenance records:
2023.02.09
* 新版本检查模块上线
"""
# ---- ---- ---- ---- ---- #
import sys
import os
import re
import codecs
import chardet
import subprocess
import shutil
import textwrap
import pandas as pd
from collections import Counter
from zipfile import ZipFile
from functools import wraps
import yaml
import inspect
import logging
import platform

YAML = "language.yaml"
LANG = "CN"  # default language, CN/EN
NONE_LIST = ["", "NA", "N/A", "NULL"]
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


def call_log(func):
    """装饰器，函数调用记录，注意，装饰后将失去IDE智能提示"""

    @wraps(func)
    def with_logging(*args, **kwargs):
        if "no_log" not in kwargs or not kwargs["no_log"]:
            print("调用 " + func.__name__)
        return func(*args, **kwargs)

    return with_logging


def _name():
    """获取正在运行函数(或方法)或类名称"""
    return inspect.stack()[1][3]


def _join_str(str_list, sep=","):
    """
    将对象元素对象转化为字符串格式，并以特定分隔符连接
    :param str_list:列表、元组、集合，目标对象
    :param sep:字符串，分隔符，以第一个字符为准
    :return: 正常返回元素连接后的长字符串
    """
    new_list = list(map(lambda x: " {0}{1}{0}".format('"', str(x)), list(str_list)))
    if len(str(sep)) > 1:
        sep = sep[0]
    # joined_str = "[{0} ]".format(sep.join(new_list)) # 字符串结果前后加[]
    joined_str = sep.join(new_list)
    return joined_str


def _wrap(err_msg: str, max_len: int = 40, head: str = " ", self_cut: bool = True, self_len=100):
    """
    预处理报错文本，根据文本长度确定是否换行
    :param err_msg: 报错文本信息
    :param max_len: 开头不添加换行符门槛的最短文本长度（优先级低于开启self_cut的self_cut_len）
    :param head: 开头头换行符前额外的字符信息
    :param self_cut: 报错语自身是否裁剪
    :param self_len: 报错语自身裁剪字符长度上限
    :return:
    """
    if self_cut and len(err_msg) > self_len:
        return f"{head}\n" + textwrap.fill(text=err_msg, width=self_len)
    else:
        return f"{head}\n{err_msg}" if len(err_msg) > max_len else err_msg


def _load_yaml(in_yaml, quiet=True):
    try:
        with open(in_yaml, encoding="utf-8") as f:
            yaml_dic = yaml.load(f, Loader=yaml.SafeLoader)
    except:
        with open(in_yaml, encoding="gbk") as f:
            yaml_dic = yaml.load(f, Loader=yaml.SafeLoader)
    print(yaml_dic) if not quiet else 1
    return yaml_dic


def _convert_size(size_str):
    """
    将M/K结尾的文件大小转换为对应字节数，不合规默认为0字节
    :param size_str:
    :return: 正常返回转换为字节后的文件大小
    """
    convert_size = 0
    spat = re.compile(r"(^[0-9]+)([A-Za-z]*$)")
    size_match = re.match(spat, str(size_str))
    if size_match:
        size_num = int(size_match.group(1))
        size_unit = str(size_match.group(2))
        size_unit = size_unit.upper()
        if size_unit == "M":
            convert_size = size_num * 1024 * 1024
        elif size_unit == "K":
            convert_size = size_num * 1024
        elif not size_unit:
            convert_size = size_num
        else:
            convert_size = 0
            logging.error("文件大小单位设置有误")
    else:
        logging.error("文件大小格式设置有误")
    return convert_size


def _get_encoding(in_file, confidence: float = 0.6, line=3000):
    """
    推测文件编码格式，（chardet）
    :param in_file: 字符串，文件名
    :param confidence: 置信度，含有中文的文件建议降低置信度，默认0.6
    :param line: 读入行数，小文件为提升准确性建议设置为-1，即全部读入，默认3000
    :return: 正常返回推测的文件编码格式（大写）
    """
    code_format = ""
    with open(in_file, "rb") as fileIN:
        test_data = fileIN.read(line)
        format_res = chardet.detect(test_data)
        if format_res["confidence"] > confidence:
            code_format = format_res["encoding"].upper()
            if re.findall('iso-8859|ascii', code_format.lower()):
                code_format = "GBK"  # 中文语境下包含各种特殊符号 # 所有编码都是兼容ASCII,统一为GBK后续读入
        elif format_res["confidence"] > 0:
            code_format = "GBK"  # 可能会报错
    return code_format


def _get_encoding2(in_file):
    """
    检测文件编码格式，备选（linux file）
    :param in_file: 字符串，文件名
    :return: 正常返回检测的文件编码格式（大写）
    """
    if platform.system() == "Linux":
        code_format = os.popen(f"file --mime-encoding {in_file}").read().rstrip('\n').split(':')[1].upper()
    elif platform.system() == "Windows":
        logging.warning("Test in linux env, or the chardet method will be forced to infer the file format instead!")
        code_format = _get_encoding(in_file)
    else:
        code_format = None
        logging.critical("Only linux and windows are supported!")
    return code_format


def _read_file(in_file, in_code, block_size=102400):
    """
    一定区块大小按照指定格式构建指定文件生成器
    :param in_file: 输入文件
    :param in_code: 读入格式
    :param block_size: *读入数据块大小
    :return: 正常返回一定区块大小的字符串的生成器，读入失败返回报错信息
    """
    in_code = in_code.upper()
    try:
        with codecs.open(in_file, "r", in_code) as fileIN:
            while True:
                content_block = fileIN.read(block_size)
                if content_block:
                    yield content_block
                else:
                    return
    except Exception as e:
        return e


def _read_line(in_file, rm_br=True):
    """
    按行读取文件
    :param in_file: 字符串，读取对象
    :param rm_br: 布尔值，是否删除行右侧换行符，默认True
    :return: 正常返回生成器（行，行号），异常返回报错信息
    """
    try:
        line_no = 0
        with codecs.open(in_file, "r", encoding='UTF-8') as fileIN:
            for line in fileIN:
                line_no += 1
                if rm_br:
                    line = line.rstrip('\r\n')  # Windows
                    line = line.rstrip('\r')  # Mac
                    line = line.rstrip('\n')  # Linux
                if line.isspace():
                    continue  # skip blank line but line_no add 1 still
                elif not line:
                    return
                else:
                    yield line, line_no
    except Exception as e:
        return e


def _row2list(file, sep="\t", row_no=1, rm_blank=True, fill_null=False, null_list: list = None):
    if isinstance(null_list, str):
        null_list = [null_list, ]
    if null_list is None:
        null_list = list(NONE_LIST)
    line_list = []
    for line, line_no in _read_line(file):
        if line_no < row_no:
            continue
        elif line_no > row_no:
            break
        else:
            if rm_blank:
                line_list = list(map(lambda x: x.strip(), line.split(sep)))
            if fill_null:
                line_list = ["NA" if x in null_list else x for x in line_list]
            return line_list


def _col2list(file, sep="\t", col_no=1, rm_blank=True, fill_null=True, null_list: list = None):
    if isinstance(null_list, str):
        null_list = [null_list, ]
    if null_list is None:
        null_list = list(NONE_LIST)
    col_elements = []
    for row, no in _read_line(file):
        row_list = row.split(sep)
        if rm_blank:
            row_list = list(map(lambda x: x.strip(), row_list))
        if fill_null:
            row_list = ["NA" if x in null_list else x for x in row_list]
        col_element = row_list[col_no - 1]
        col_elements.append(col_element)
    return col_elements


def _path_pre_proc(path: str):
    """
    路径预处理，删除前后空白，及结尾路径符号
    :param path: 字符串，路径对象
    :return: 处理后路径对象
    """
    path = path.strip()
    path = path.rstrip("/")
    path = path.rstrip("\\")
    path = path.rstrip("\\\\")
    return path


def _pre_class(cls, quiet=True):
    """装饰器，赋值报错字典"""
    cls.lang_dic = _load_yaml(os.path.join(os.path.dirname(__file__), YAML), quiet=quiet)
    # print("- 调用", cls.__name__, "检查")  # 仅导入时打印，无意义
    return cls


@_pre_class
class Str(object):
    """check Str"""

    def __init__(self, in_str: str, other_str="", add_info="", no_log=False, lang=LANG):
        """
        字符串类型数据检查
        check tools for STR
        :param in_str: 字符串，检查对象
        :param other_str: 字符串，报错信息中替换输入字符串为其他内容，""表示不替换，显示输入字符串
        :param add_info: 字符串，附加信息
        :param no_log: 不打印调用及报错信息，默认为False
        :param lang: 字符串，选择报错语言，可选["CN", "EN"]，默认CN
        """
        self.in_str = in_str
        self.other_str = other_str
        self.add_info = add_info
        self.no_log = no_log
        self.lang = lang
        self._c = self.__class__.__name__  # 类名
        self._e = self.lang_dic[self.lang][self._c]  # 报错字典初定位

    def __repr__(self):
        return 'Str(in：{0.in_str!r}, show：{0.other_str!r}, add：{0.add_info!r}, ' \
               'quiet：{0.no_log!r}, lang：{0.lang!r})'.format(self)

    def __str__(self):
        return '(in：{0.in_str!s}, show：{0.other_str!s}, add：{0.add_info!s}, ' \
               'quiet：{0.no_log!s}, lang：{0.lang!s})'.format(self)

    def length(self, elen: int = None, min_len: int = 1, max_len: int = 20):
        """
        判断字符串长度是否在范围内（max_len应大于等于min_len）
        :param elen: 整数，字符串长度固定值，优先级高于范围检查，None表示不检查固定值
        :param min_len: 整数，字符串长度下限，默认1
        :param max_len: 整数，字符串长度上限，默认20
        :return: 范围内返回0，范围外返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            s_str = self.other_str if self.other_str else self.in_str
            if elen is not None:
                if len(self.in_str) == elen:
                    return 0
                else:
                    return f"{self.add_info}{s_str}{self._e['长度']}{len(self.in_str)}{self._e['要求']}{elen}"
            elif len(self.in_str) >= min_len:
                if len(self.in_str) <= max_len:
                    return 0
                else:
                    return f"{self.add_info}{s_str}{self._e['长度']}{len(self.in_str)}{self._e['超出']}{max_len}"
            else:
                return f"{self.add_info}{s_str}{self._e['长度']}{len(self.in_str)}{self._e['低于']}{min_len}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['length']}"

    def format(self, re_obj=None, re_ban_body=None, ck_head=True, re_ban_head=None,
               ck_tail=False, re_ban_tail=None):
        """
        字符串正则范围内检查（默认以字母/非零数字开头，仅包含字母、数字、点和中划线）
        :param re_obj: re.compile对象，允许的正则格式编译，默认re.compile(r"^[A-Za-z1-9][A-Za-z0-9-.]*$")
        :param re_ban_body: re.compile对象，错误的主体字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9-.]")
        :param ck_head: 布尔值，是否检查字符串首个字符，默认True
        :param re_ban_head: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"^[^A-Za-z1-9]")
        :param ck_tail: 布尔值，是否检查字符串末尾字符，默认False
        :param re_ban_tail: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9]$")
        :return: 范围内返回0，范围外返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            s_str = self.other_str if self.other_str else self.in_str
            if re_obj is None:
                re_obj = re.compile(r"^[A-Za-z1-9][A-Za-z0-9-.]*$")
                if re_ban_body is None:
                    re_ban_body = re.compile(r"[^A-Za-z0-9-.]")
                if ck_head and re_ban_head is None:
                    re_ban_head = re.compile(r"^[^A-Za-z1-9]")
                if ck_tail and re_ban_tail is None:
                    re_ban_tail = re.compile(r"[^A-Za-z0-9]$")
                if not ck_head:
                    re_ban_head = re_ban_body
            if re.match(re_obj, self.in_str):
                return 0
            else:
                msg1 = ""
                msg2 = ""
                msg3 = ""
                ill_list = re.findall(re_ban_body, self.in_str)
                if ill_list:
                    msg1 = f"{self.add_info}{s_str}{self._e['非法']}{_wrap(_join_str(ill_list))}；"
                ill_start = re.findall(re_ban_head, self.in_str)
                if ill_start:
                    msg2 = f"{self.add_info}{s_str}{self._e['非法起始']}{_join_str(ill_start)}"
                if ck_tail:
                    ill_end = re.findall(re_ban_tail, self.in_str)
                    if ill_end:
                        msg3 = f"{self.add_info}{s_str}{self._e['非法结尾']}{_join_str(ill_start)}"
                msg = msg1 + msg2 + msg3
                if not msg:
                    msg = f"{self.add_info}{s_str}{self._e['非法未知']}"
                return msg
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['format']}"

    def chinese(self):
        """
        字符串中是否有中文检查
        :return: 无中文返回0，有中文返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            s_str = self.other_str if self.other_str else self.in_str
            in_str = str(self.in_str)
            str_list = []
            for i_str in in_str:
                if "\u4e00" <= i_str <= "\u9fa5":
                    str_list.append(i_str)
            if len(str_list) != 0:
                return f"{self.add_info}{s_str}{self._e['中文']}{_wrap(_join_str(str_list))}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['chinese']}"

    def ban(self, ban_list=None):
        """
        便捷字符串禁用字符检查（完整版使用format）
        :param ban_list: 迭代器，所有不支持的字符，None表示无禁用
        :return:无禁用返回0，有禁用返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            s_str = self.other_str if self.other_str else self.in_str
            if ban_list is None:
                ban_list = []
            error_list = []
            for i in ban_list:
                if str(i) in self.in_str:
                    error_list.append(i)
            if not error_list:
                return 0
            else:
                return f"{self.add_info}{s_str}{self._e['禁用']}{_wrap(_join_str(error_list))}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['ban']}"

    def check(self, ck_length=True, ck_format=True,
              ck_chinese=True, ck_ban=True, allow_space=False,
              elen: int = None, min_len: int = 1, max_len: int = 20,
              re_obj=None, re_ban_body=None, ck_head=True, re_ban_head=None,
              ban_list: list = None):
        """
        字符串检查
        :param ck_length: 布尔值，是否检查长度，默认True
        :param ck_format: 布尔值，是否检查正则格式，默认True（以字母/非零数字开头，仅包含字母、数字、点和中划线）
        :param ck_chinese: 布尔值，是否检查中文字符，默认True
        :param ck_ban: 布尔值，是否检查禁用字符，默认True
        :param allow_space: 布尔值，是否允许空格，默认False
        :param elen: 整数，字符串长度固定值，优先级高于范围检查，None表示不检查固定值
        :param min_len: 整数，字符串长度下限，默认1
        :param max_len: 整数，字符串长度上限，默认20
        :param re_obj: re.compile对象，允许的正则格式编译，默认re.compile(r"^[A-Za-z1-9][A-Za-z0-9-.]*$")
        :param re_ban_body: re.compile对象，错误的主体字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9-.]")
        :param ck_head: 布尔值，是否检查字符串首个字符
        :param re_ban_head: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"^[^A-Za-z1-9]")
        :param ban_list: 迭代器，所有不支持的字符，None表示不检查禁用字符，忽视ck_ban
        :return: 符合期望返回0，不符合返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            error_list = []
            if not ck_chinese:  # 如果不禁用中文字符，那么将所有中文字符替换为"a",规避正则检查
                self.in_str = re.sub('[\u4e00-\u9fa5]', 'a', self.in_str)
            if allow_space:  # 如果允许空格，那么将所有空格替换为"b",规避正则检查
                self.in_str = re.sub(' ', 'b', self.in_str)
            if ck_length:
                print(elen)
                err_msg = self.length(elen=elen, max_len=max_len, min_len=min_len)
                if err_msg:
                    error_list.append(f"{self.add_info}{err_msg}")
            if ck_format:
                err_msg = self.format(re_obj=re_obj, re_ban_body=re_ban_body,
                                      ck_head=ck_head, re_ban_head=re_ban_head)
                if err_msg:
                    error_list.append(f"{self.add_info}{err_msg}")
            if ck_chinese:
                err_msg = self.chinese()
                if err_msg:
                    error_list.append(f"{self.add_info}{err_msg}")
            if ck_ban and ban_list is not None:
                err_msg = self.ban(ban_list=ban_list)
                if err_msg:
                    error_list.append(f"{self.add_info}{err_msg}")
            if len(error_list) == 0:
                return 0
            else:
                return error_list
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['check']}", ]


@_pre_class
class Num(object):
    """check Num"""

    def __init__(self, in_num: float, add_info="", no_log=False, lang=LANG):
        """
        数值类型数据检查
        check tools for Num
        :param in_num: 字符串，检查对象
        :param add_info: 字符串，附加信息
        :param no_log: 不打印调用及报错信息，默认为False
        :param lang: 字符串，选择报错语言，可选["CN", "EN"]，默认CN
        """
        self.in_num = in_num
        self.add_info = add_info
        self.no_log = no_log
        self.lang = lang
        self._c = self.__class__.__name__  # 类名
        self._e = self.lang_dic[self.lang][self._c]  # 报错字典初定位

    def __repr__(self):
        return 'Num(in：{0.in_num!r}, add：{0.add_info!r}, ' \
               'quiet：{0.no_log!r}, lang：{0.lang!r})'.format(self)

    def __str__(self):
        return '(in：{0.in_num!s}, add：{0.add_info!s}, ' \
               'quiet：{0.no_log!s}, lang：{0.lang!s})'.format(self)

    def range(self, min_num=float('-inf'), max_num=float('inf')):
        """
        数值范围内检查
        :param min_num: 浮点数，取值下限
        :param max_num: 浮点数，取值上限
        :return: 范围内返回0，范围外返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if min_num <= self.in_num <= max_num:
                return 0
            else:
                min_num = self._e['负无穷'] if min_num == float('-inf') else min_num
                max_num = self._e['正无穷'] if max_num == float('inf') else max_num
                return f"{self.add_info}{self._e['下限']}{min_num}{self._e['上限']}{max_num}" \
                       f"{self._e['设定值']}{self.in_num}{self._e['超限']}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['range']}"

    def ban(self, ban_num: list = None):
        """
        数值禁用值检查
        :param ban_num: 数值/数值列表，所有不支持的数值，None表示无禁用
        :return: 无禁用返回0，有禁用返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if not isinstance(ban_num, list):
                ban_num = [ban_num, ]
            if ban_num is None:
                ban_num = []
            error_list = []
            for i in ban_num:
                if i == float(self.in_num):
                    error_list.append(i)
            if not error_list:
                return 0
            else:
                return f"{self.add_info}{self._e['禁用']}{_wrap(_join_str(error_list))}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['ban']}"

    def check(self, ck_range=True, ck_ban=True, min_num=float('-inf'), max_num=float('inf'), ban_num: list = None):
        """
        数值检查
        :param ck_range: 布尔值，是否检查大小范围，默认True
        :param ck_ban: 布尔值，是否检查禁用值，默认True
        :param min_num: 浮点数，取值下限，默认负无穷
        :param max_num: 浮点数，取值上限，默认正无穷
        :param ban_num: 数值/数值列表，所有不支持的数值，None表示不检查禁用值，忽视ck_ban
        :return: 符合期望返回0，不符合返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            error_list = []
            if ck_range is True:
                err_msg = self.range(min_num=min_num, max_num=max_num)
                if err_msg:
                    error_list.append(f"{err_msg} ")
            if ck_ban and ban_num is not None:
                err_msg = self.ban(ban_num=ban_num)
                if err_msg:
                    error_list.append(f"{err_msg} ")
            if len(error_list) == 0:
                return 0
            else:
                return error_list
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['check']}", ]


@_pre_class
class File(object):
    """check File"""

    def __init__(self, in_file, sep="\t", add_info="", no_log=False, lang=LANG):
        """
        字符串类型数据检查
        check tools for File
        :param in_file: 字符串，检查对象，例如："D:/a.txt"
        :param sep: 字符串，指定行元素间分隔符，默认"\t"
        :param add_info: 字符串，附加信息
        :param no_log: 不打印调用及报错信息，默认为False
        :param lang: 字符串，选择报错语言，可选["CN", "EN"]，默认CN
        """
        self.in_file = os.path.abspath(in_file)
        self.sep = sep
        self.add_info = add_info
        self.no_log = no_log
        self.lang = lang
        self._c = self.__class__.__name__  # 类名
        self._e = self.lang_dic[self.lang][self._c]  # 报错字典初定位
        self.__name = os.path.basename(in_file)
        if not os.path.isfile(in_file):
            print("Warning: Input Is Not A File! [%s]".format(in_file))

    def __repr__(self):
        return 'File(in：{0.in_file!r}, sep：{0.sep!r}, add：{0.add_info!r}, ' \
               'quiet：{0.no_log!r}, lang：{0.lang!r})'.format(self)

    def __str__(self):
        return '(in：{0.in_file!s}, sep：{0.sep!r}, add：{0.add_info!s}, ' \
               'quiet：{0.no_log!s}, lang：{0.lang!s})'.format(self)

    def exist(self):
        """
        文件存在检查
        :return: 存在返回0，不存在返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if os.path.isfile(self.in_file):
                return 0
            else:
                return f"{self.add_info}{self._e['输入']}{self.__name}{self._e['不存在']}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['exist']}"

    def suffix(self, suffix_list: list = None):
        """
        文件后缀名检查（检查in_file是否以suffix_list中某一个元素结尾，不区分大小写）
         :param suffix_list: 字符串/字符串列表，允许使用的格式名，不区分大小写，默认txt
        :return: 匹配到返回0，否则返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if suffix_list is None:
                suffix_list = ['txt', ]
            if isinstance(suffix_list, str):
                suffix_list = [suffix_list.lower(), ]
            else:
                suffix_list = list(map(lambda x: x.lower(), suffix_list))
            for i_suf in suffix_list:
                re_obj = re.compile(str(i_suf) + r"$")
                if re.search(re_obj, self.in_file):
                    return 0
            return f"{self.add_info}{self.__name}{self._e['不支持后缀']}{self._e['支持后缀']}{_wrap(_join_str(suffix_list))}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['suffix']}"

    def null(self):
        """
        判断是否为空文件
        :return: 非空返回0，空返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if os.path.getsize(self.in_file) == 0:
                return f"{self.add_info}{self._e['输入']}{self.__name}{self._e['空文件']}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['null']}"

    def size(self, max_size="50M"):
        """
        检查文件大小是否超出限制
         :param max_size: 字符串，以K/M结尾，文件大小上限，默认"50M"
        :return: 未超出返回0，超出返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            max_byte = _convert_size(max_size)
            doc_size = os.path.getsize(self.in_file)
            if doc_size > max_byte:
                return f"{self.add_info}{self._e['输入']}{self.__name}{self._e['大小']}{doc_size}" \
                       f"{self._e['超上限']}{max_size}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['size']}"

    def encoding(self, allowed_encode: list = None, use_1=False):
        """
        检查编码格式是否在允许范围内（默认UTF-8）（二进制文件如xlsx，无法检测文件编码）
        :param allowed_encode: 字符串/字符串列表，允许的编码格式，不区分大小写,默认UTF-8
        :param use_1: 布尔值，默认False，True表示使用python.chardet模块推测文件编码，False表示使用linux.file命令获取文件编码
        :return: 范围内返回0，范围外返回字符串，推测的文件编码格式（大写），二进制文件返回None
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if allowed_encode is None:
                allowed_encode = ["UTF-8", ]  # ["UTF-8", "GBK", "GB2312"]
            if isinstance(allowed_encode, str):
                allowed_encode = [allowed_encode.upper(), ]
            else:
                allowed_encode = list(map(lambda x: x.upper(), allowed_encode))
            if use_1:
                doc_encoding = _get_encoding(self.in_file)
            else:
                doc_encoding = _get_encoding2(self.in_file)
            if doc_encoding in allowed_encode:
                return 0
            else:
                return doc_encoding
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['encoding']}"

    def convert(self, in_code: str = "UTF-8", out_file=None, out_code="UTF-8"):
        """
        文件编码转换
        :param in_code: 字符串，输入文件编码，不区分大小写，默认"UTF-8"，云平台前端限制：txt文件仅UTF-8及UTF-8-BOM可上传
        :param out_file: 字符串，输出对象，例如："D:/b.txt"，默认在in_file后添加".convert"
        :param out_code: 字符串，输出文件编码，目标格式，不区分大小写，默认"UTF-8"
        :return: 正常返回0，失败返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if out_file is None:
                out_file = str(self.in_file) + '.convert'
            flag = ''
            if os.path.abspath(self.in_file) == os.path.abspath(out_file):
                flag += '1'
                out_file = str(out_file) + '.convert'
            # if not in_code:
            #     return f"{self.add_info}{self.__name}编码格式不被支持，请转为{out_code}编码后重试"
            in_code = in_code.upper()
            out_code = out_code.upper()
            logging.info(f"File {self.__name} encoding {in_code} -> {out_code}")
            try:
                with codecs.open(out_file, "w", out_code) as fileOU:
                    for i in _read_file(self.in_file, in_code=in_code):
                        if isinstance(i, Exception):
                            return repr(i)
                        fileOU.write(i)
                if flag:
                    os.system(f'cp -r {out_file} {self.in_file}')
                    os.system(f'rm {out_file}')
                return 0
            except Exception as e:
                print(e)
                return f"{self.add_info}{self.__name}{self._e['从']}{in_code}{self._e['到']}{out_code}{self._e['转码出错']}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['convert']}"

    convert_encoding = convert

    def xlsx2txt(self, out_file: str = None, sheet_no=1, sep: str = None, na_values: list = None, na_rep=""):
        """
        文件格式转换（xlsx to txt）
        :param out_file: 字符串，输入对象，例如："D:/a.txt"，None表示输出为同名但后缀为txt的文件
        :param sheet_no: 正整数，转换的sheet表号，默认1
        :param sep: 字符串，输出文件分隔符，默认同对象参数，为"\t"
        :param na_values: 字符串列表，in_file中表示缺失值的字符串，默认None，表示维持原样，无默认缺失
        :param na_rep: 字符串，out_file中表示缺失值的字符串，默认""
        :return: 转换成功返回0，转换失败返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1

        if sep is None:
            sep = self.sep
        try:
            if out_file is None:
                out_file = os.path.splitext(self.in_file)[0] + '.txt'
            df = pd.read_excel(self.in_file, sheet_name=sheet_no - 1, keep_default_na=False, na_values=na_values)
            df.to_csv(out_file, sep=sep, na_rep=na_rep, index=False, quotechar=sep)
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['输入']}{self.__name}: {self._e['xlsx2txt']}"
        else:
            return 0

    def check_base(self, ck_exist=True, ck_suffix=True, ck_null=True,
                   ck_size=True, ck_encoding=True, use_1=False, do_convert=True,
                   suffix_list: list = None,
                   max_size="50M",
                   allowed_encode: list = None,
                   out_file=None, out_code="UTF-8"):
        """
        文件基础检查（存在，后缀，空文件，大小，编码）,提供转码选项(仅use_1=True消除BOM)，仅当提供一种allowed_encode时有效
        注意：文件编码检查及转码仅对非二进制文件有效，xlsx文件推荐使用file_xlsx2txt函数转换后进行文件检查
        注意：如果out_file与in_file同路径且同名，将覆盖原文档
        :param ck_exist: 布尔值，是否检查存在，默认True
        :param ck_suffix: 布尔值，是否检查后缀，默认True
        :param ck_null: 布尔值，是否检查空文件，默认True
        :param ck_size: 布尔值，是否检查大小，默认True
        :param ck_encoding: 布尔值，是否检查编码格式，默认True
        :param use_1: 布尔值，默认False，True表示使用python.chardet模块推测文件编码，False表示使用linux.file命令获取文件编码
        :param do_convert: 布尔值，当检查到编码格式不符合期望编码格式时，是否进行转码，仅当提供一种allowed_encode时有效，默认True
        :param suffix_list: 字符串/字符串列表，允许使用的格式名，不区分大小写，默认txt
        :param max_size: 字符串，以K/M结尾，文件大小上限，默认"50M"
        :param allowed_encode: 字符串/字符串列表，允许的编码格式，不区分大小写，默认[UTF-8,]，不建议使用ASCII
        :param out_file: 字符串，输出对象,例如："D:/b.txt"，默认在in_file后添加".convert"
        :param out_code: 字符串，输出文件编码，默认UTF-8
        :return: 符合期望返回0，不符合返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        if allowed_encode is None:
            allowed_encode = ["UTF-8", ]
        if isinstance(allowed_encode, str):
            allowed_encode = [allowed_encode.upper(), ]
        try:
            error_list = []
            if ck_exist:
                err_msg = self.exist()
                if err_msg:
                    error_list.append(f"{err_msg}")
            if ck_suffix:
                err_msg = self.suffix(suffix_list=suffix_list)
                if err_msg:
                    error_list.append(f"{err_msg}")
            if ck_null:
                err_msg = self.null()
                if err_msg:
                    error_list.append(f"{err_msg}")
            if ck_size:
                err_msg = self.size(max_size=max_size)
                if err_msg:
                    error_list.append(f"{err_msg}")
            if ck_encoding:
                err_msg = self.encoding(allowed_encode=allowed_encode, use_1=use_1)
                if err_msg is None:
                    error_list.append(
                        f"{self.add_info}{self._e['推测']}{self.__name}{self._e['二进制']}")
                elif do_convert and len(allowed_encode) == 1:
                    if err_msg:
                        in_code = err_msg  # 当UTF-8文件存在少量中文或特殊符号时，使用use_1=True可能存在识别不准确的问题
                        # in_code = "UTF-8"  # 云平台前端限制txt文件编码仅可为UTF-8或UTF-8-BOM，这里可默认UTF-8
                    else:
                        in_code = allowed_encode[0]
                    err_msg = self.convert(out_file=out_file, in_code=in_code, out_code=out_code)
                    if err_msg:
                        error_list.append(f"{err_msg}")
                elif err_msg and not do_convert:
                    error_list.append(
                        f"{self.add_info}{self._e['推测编码']}{err_msg}{self._e['或']}ASCII"
                        f"{self._e['转换重试']}{allowed_encode}")
            if len(error_list) == 0:
                return 0
            else:
                return error_list
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['check_base']}", ]

    def get_row_num(self):
        """
        获取文件行数
        :return: 正常返回整数
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        if platform.system() == "Windows":
            logging.error("需要用到Linux系统命令awk，否则强制替换行为4")
            return 4
        try:
            out = subprocess.getoutput("awk 'END{print NR}' %s" % self.in_file)
            return int(out.split()[0])
        except Exception as e:
            print(e) if not self.no_log else 1

    def get_col_num(self):
        """
        获取文件列数（列数不一致时，以最后一行统计为准）
        :return: 正常返回整数
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        if platform.system() == "Windows":
            logging.error("需要用到Linux系统命令awk，否则强制替换列为3")
            return 3
        try:
            out = subprocess.getoutput("awk -F '%s' 'END{print NF}' %s" % (self.sep, self.in_file))
            return int(out)
        except Exception as e:
            print(e) if not self.no_log else 1

    def get_line(self, line_num=1):
        """
        获取文件指定一行（整行作为字符串读入），默认读第一行
        :param line_num: 正整数，指定读取行号，默认1
        :return: 正常返回指定行字符串，错误无返回
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            for line, line_no in _read_line(self.in_file, rm_br=True):
                if line_no < line_num:
                    continue
                elif line_no > line_num:
                    return None
                else:
                    return line
        except Exception as e:
            print(e) if not self.no_log else 1

    get_row = get_row_line = get_line

    def line_dup(self):
        """
        数据重复行检查
        :return: 无重复返回0，有重复返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            res_list = []
            err = []
            for line, line_no in _read_line(self.in_file):
                if line in res_list:
                    err.append(line_no)
                else:
                    res_list.append(line)
            if err:

                return f"{self.add_info}{self._e['输入']}{self.__name}" \
                       f"{self._e['重复行号']}{_wrap(_join_str(err), self_len=160)}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['line_dup']}"

    def line_blank(self, in_line):
        """
        空白行检查（除空白字符外，无其他内容）
        :param in_line: 字符串，检查对象，可通过File.get_row_line获得
        :return: 非空白行返回0，空白行返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            in_line = in_line.strip()
            blank_pat = re.compile(r"^\s*$")
            if re.search(blank_pat, in_line):
                return f"{self.add_info}{self._e['空白行']}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['line_blank']}"

    def line_sep(self, in_line, sep_r=r'\t'):
        """
        分隔符规范检查（开头分隔符、连用分隔符、分隔符前后空白、结尾空白）
        :param in_line: 字符串，检查对象，可通过File.get_row_line获得
        :param sep_r: 字符串，纯文本读入的分隔符，含有与正则有关的字符应在字符串前加r,或将字符使用'\'转义,默认r'\t'
        :return: 规范返回0，不规范返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            head_sep = re.compile(f"^[{sep_r}]")
            sep_sep = re.compile(f"{sep_r}{sep_r}")
            blank_sep = re.compile(rf"\s{sep_r}")
            sep_blank = re.compile(rf"{sep_r}\s")
            tail_blank = re.compile(r"\s$")
            msg = ''
            if re.search(head_sep, in_line):
                msg = msg + f"{self._e['开头符']}{sep_r};"
            if re.search(sep_sep, in_line):
                msg = msg + f"{self._e['连续符']}{sep_r};"
            if re.search(blank_sep, in_line):
                msg = msg + f"{sep_r}{self._e['符前空白']}"
            if re.search(sep_blank, in_line):
                msg = msg + f"{sep_r}{self._e['符后空白']}"
            if re.search(tail_blank, in_line):
                msg = msg + f"{self._e['空白结尾']}"
            if msg == "":
                return 0
            else:
                return f'{self.add_info}{msg}'
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['line_sep']}"

    def get_row2list(self, row_no=1, rm_blank=True, fill_null=False, null_list: list = None):
        """
        获取文件指定一行的元素列表，并默认移除元素前后空白，默认第一行
        :param row_no: 正整数，指定读取行号，默认1
        :param rm_blank: 布尔值，是否移除该行元素前后空白，默认True
        :param fill_null: 布尔值，是否将缺失数据统一替换为NA，默认False
        :param null_list: 字符串/字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
        :return: 正常返回指定行元素列表，错误无返回
        """
        try:
            if isinstance(null_list, str):
                null_list = [null_list, ]
            if null_list is None:
                null_list = list(NONE_LIST)
            return _row2list(self.in_file, self.sep, row_no, rm_blank, fill_null, null_list)
            # line_list = []
            # for line, line_no in _read_line(self.in_file):
            #     if line_no < row_no:
            #         continue
            #     elif line_no > row_no:
            #         break
            #     else:
            #         if rm_blank:
            #             line_list = list(map(lambda x: x.strip(), line.split(self.sep)))
            #         if fill_null:
            #             line_list = ["NA" if x in null_list else x for x in line_list]
            #         return line_list
        except Exception as e:
            print(e) if not self.no_log else 1

    def get_col2list(self, col_no=1, rm_blank=True, fill_null=True, null_list: list = None):
        """
        获取文件指定一列的元素列表，并默认移除元素前后空白，默认第一列
        :param col_no: 正整数，指定读取行号，默认1
        :param rm_blank: 布尔值，是否移除该列元素前后空白，默认True
        :param fill_null: 布尔值，是否将缺失数据统一替换为NA，默认True
        :param null_list: 字符串/字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
        :return: 正常返回指定列元素列表，错误无返回
        """
        try:
            if isinstance(null_list, str):
                null_list = [null_list, ]
            if null_list is None:
                null_list = list(NONE_LIST)
            return _col2list(self.in_file, self.sep, col_no, rm_blank, fill_null, null_list)
            # col_elements = []
            # for row, no in _read_line(self):
            #     row_list = row.split(self.sep)
            #     if rm_blank:
            #         row_list = list(map(lambda x: x.strip(), row_list))
            #     if fill_null:
            #         row_list = ["NA" if x in null_list else x for x in row_list]
            #     col_element = row_list[col_no - 1]
            #     col_elements.append(col_element)
            # return col_elements
        except Exception as e:
            print(e) if not self.no_log else 1

    def com_dim(self, row_greater: bool = None, contain_equal=True):
        """
        数据行列数大小关系检查
        :param row_greater: 布尔值，是否行数更多，None表示仅返回比较结果信息，不返回报错信息
        :param contain_equal: 布尔值，是否含等号，作为row_greater参数补充，仅在不为None时生效，默认True
        :return: 正常[有row_greater参数返回0,无row_greater参数返回字符串检查结果]，异常返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            row_number = self.get_row_num()
            col_number = self.get_col_num()
            if row_greater is None:
                if row_number > col_number:
                    return f"{self.add_info}{self._e['行多']}"
                elif row_number > col_number:
                    return f"{self.add_info}{self._e['列多']}"
                else:
                    return f"{self.add_info}{self._e['同维']}"
            elif row_greater:
                if contain_equal:
                    if row_number < col_number:
                        return f"{self.add_info}{self._e['行不少于列']}"
                    else:
                        return 0
                elif row_number <= col_number:
                    return f"{self.add_info}{self._e['行大于列']}"
                else:
                    return 0

            else:
                if contain_equal:
                    if row_number > col_number:
                        return f"{self.add_info}{self._e['行不多于列']}"
                    else:
                        return 0
                elif row_number >= col_number:
                    return f"{self.add_info}{self._e['行小于列']}"
                else:
                    return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['com_dim']}"

    com_row_col_num = com_dim

    def check_dim(self, row_num_exp: int = None, col_num_exp: int = None):
        """
        数据固定维度快捷检查，完整版使用 check_file_content
        :param row_num_exp: 正整数，期望行数，None表示不检查行数
        :param col_num_exp: 正整数，期望列数，None表示不检查列数
        :return: 符合期望返回0，不符合返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            error_list = []
            row_number = self.get_row_num()
            col_number = self.get_col_num()
            if row_num_exp is not None:
                if row_number != row_num_exp:
                    error_list.append(f"{self.add_info}{self.__name}{self._e['行数应为']}{row_num_exp}")
            if col_num_exp is not None:
                if col_number != col_num_exp:
                    error_list.append(f"{self.add_info}{self.__name}{self._e['列数应为']}{col_num_exp}")
            if len(error_list) == 0:
                return 0
            else:
                return error_list
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['check_dim']}", ]

    def check_line_fix(self, rm_blank=True, fill_null=False, null_list=None,
                       ck_row_fix=True, ck_col_fix=True, set_range=False,
                       range_min=1, range_max: int = None,
                       row_fix_no: int = 1, row_fix_content: list = None,
                       col_fix_no: int = 1, col_fix_content: list = None):
        """
        数据固定行/列标题快捷检查，完整版使用 check_file_content，较完整版多出部分行/列内容固定的检查
        :param rm_blank: 布尔值，是否移除该列元素前后空白，默认True
        :param fill_null: 布尔值，是否将缺失数据统一替换为NA，默认True
        :param null_list: 字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
        :param ck_row_fix: 布尔值，是否检查行标题，默认True
        :param ck_col_fix: 布尔值，是否检查列标题，默认True
        :param set_range: 布尔值，是否设置检查范围，默认False
        :param range_min: 正整数，检查范围下限，set_range为True时生效，默认为1
        :param range_max: 正整数，检查范围上限，set_range为True时生效，默认为范围下限+固定内容长度
        :param row_fix_no: 正整数，要检查的行数，默认1
        :param row_fix_content: 字符串/字符串列表，期望的检查行固定内容，None表示不检查，忽视ck_row_fix
        :param col_fix_no: 正整数，要检查的列数，默认1
        :param col_fix_content: 字符串/字符串列表，期望的检查列固定内容，None表示不检查，忽视ck_col_fix
        :return: 符合期望返回0，不符合返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            # global min_index, max_index
            min_index = 1
            error_list = []
            if set_range:
                min_index = range_min - 1
            if set_range and range_max is not None:
                max_index = range_max - 1
            if ck_row_fix and row_fix_content is not None:
                in_list = self.get_row2list(row_no=row_fix_no, rm_blank=rm_blank,
                                            fill_null=fill_null, null_list=null_list)
                if isinstance(row_fix_content, str):
                    row_fix_content = [row_fix_content, ]
                if "max_index" not in vars():
                    max_index = min_index + len(row_fix_content)
                if in_list[min_index:max_index] != list(row_fix_content):
                    allowed_title = "\t".join(list(map(lambda x: str(x), row_fix_content)))
                    if set_range:
                        msg = f"{self.add_info}{self.__name}{self._e['第行']}{row_fix_no}{self._e['行']}" \
                              f"{self._e['第']}{range_min}{self._e['至']}{max_index + 1}" \
                              f"{self._e['元素须为']}{_wrap(allowed_title)}"
                        error_list.append(msg)
                    else:
                        error_list.append(f"{self.add_info}{self.__name}{self._e['第行']}{row_fix_no}"
                                          f"{self._e['行须为']}{_wrap(allowed_title)}")
            if ck_col_fix and col_fix_content is not None:
                in_list = self.get_col2list(col_no=col_fix_no, rm_blank=rm_blank,
                                            fill_null=fill_null, null_list=null_list)
                if isinstance(col_fix_content, str):
                    col_fix_content = [col_fix_content, ]
                if "max_index" not in vars():
                    max_index = min_index + len(col_fix_content)
                if in_list[min_index:max_index] != list(col_fix_content):
                    allowed_title = "\t".join(list(map(lambda x: str(x), col_fix_content)))
                    if set_range:
                        msg = f"{self.add_info}{self.__name}{self._e['第列']}{col_fix_no}{self._e['列']}" \
                              f"{self._e['第']}{range_min}{self._e['至']}{max_index + 1}" \
                              f"{self._e['元素须为']}{_wrap(allowed_title)}"
                        error_list.append(msg)
                    else:
                        error_list.append(f"{self.add_info}{self.__name}{self._e['第列']}{col_fix_no}"
                                          f"{self._e['列须为']}{_wrap(allowed_title)}")
            if len(error_list) == 0:
                return 0
            else:
                return error_list
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['check_line_fix']}", ]

    check_heading = check_line_fix

    def pre_check_content(self, out_dir, new_file=None, encoding="utf-8", rm_space: bool = True):
        """
        文件详细内容检查预处理，自动消除BOM，注意new_file与in_file为同一文件时，处理后将会替换旧文件，已内置于check_file_content
        :param out_dir: 字符串，处理后对象输出目录，推荐os.path.join(args.outdir,"tmp/analysis")
        :param new_file: 字符串，处理后对象名，将保存到out_dir目录下,默认与原文件同名
        :param encoding: 字符串，输入及输出文件编码格式，不区分大小写,默认utf-8，不推荐修改
        :param rm_space: 布尔值，是否去除元素前后空格，影响检查速度，默认True
        :return: 正常返回0，异常返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            encoding = encoding.lower()
            if new_file is None:
                new_file = os.path.join(os.path.abspath(out_dir), self.__name)
            else:
                new_file = os.path.join(os.path.abspath(out_dir), os.path.basename(new_file))
            if self.in_file == new_file:  # 去空白行
                cmd = f'sed -i "/^\s*$/d" {new_file}'
            else:
                cmd = f'mkdir -p {out_dir} && cp {self.in_file} {new_file} && sed -i "/^\s*$/d" {new_file}'
            if platform.system() == "Linux":
                print(cmd) if not self.no_log else 1
                os.system(cmd)
            else:
                logging.warning("Test in linux env, otherwise blank lines will not be removed !")
                if self.in_file != new_file:
                    cmd = f'mkdir {out_dir} && copy {self.in_file} {new_file}'
                    print(cmd) if not self.no_log else 1
                    os.system(cmd)
            df = pd.read_csv(new_file, sep=self.sep, header=None, na_filter=False, encoding=encoding,
                             na_values="", dtype='str', keep_default_na=False)
            df.columns = list(map(str, df.columns.tolist()))
            if rm_space:
                df_col = df.columns.str.strip().tolist()
                df.columns = df_col
                for col in df_col:
                    df.loc[:, col] = df[col].str.strip()
            df.to_csv(new_file, sep=self.sep, index=0, header=None, quotechar=self.sep)
        except pd.errors.ParserError as e:
            print(e) if not self.no_log else 1
            list1 = str(e).strip().split(' ')
            sep = f"{self._e['制表符']}" if self.sep == "\t" else self.sep
            sep = f"{self._e['空格']}" if self.sep == " " else sep
            return f"{self.add_info}{self._e['首行列数']}{list1[-7]}{self._e['检测到']}{list1[-3].strip(',')}" \
                   f"{self._e['列数']}{list1[-1]}\n{self._e['列数要求']}\n" \
                   f"{self._e['1.唯一']}{sep}\n{self._e['2.']}{list1[-3].strip(',')}{self._e['错用']}{sep}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['pre_check_content']}"
        else:
            return 0

    def check_content(self, out_dir, new_file=None, pre_check=True, rm_space: bool = True,
                      rm_blank=True, fill_null=False, null_list=None,
                      ck_sep=False, sep_r=r'\t', ck_header=False, ck_line_dup=False, ck_row_num=True, ck_col_num=True,
                      row_num_exp: int = None, col_num_exp: int = None,
                      row_min_num_exp: int = None, col_min_num_exp: int = None,
                      row_max_num_exp: int = None, col_max_num_exp: int = None,
                      ck_row_base=True, ck_col_base=True, ck_row_list: list = 1, ck_col_list: list = 1,
                      ck_row_length=True, ck_row_length_range=True, ck_row_dup=True, ck_row_na=True, ck_row_ban=True,
                      ck_col_length=True, ck_col_length_range=True, ck_col_dup=True, ck_col_na=True, ck_col_ban=True,
                      row_length: int = None, row_min_len=0, row_max_len: int = float('inf'),
                      col_length: int = None, col_min_len=0, col_max_len: int = float('inf'),
                      ban_list: list = None, na_list: list = None,
                      ck_row_fix=True, ck_col_fix=True, row_fix_no: int = 1, col_fix_no: int = 1,
                      row_fix_content: list = None, col_fix_content: list = None,
                      ck_row_type=False, ck_col_type=False,
                      ck_row_type_list: list = None, ck_col_type_list: list = None, exp_type='float', rm_first=False,
                      ck_row_num_range=False, ck_col_num_range=False,
                      row_min_num=float('-inf'), row_max_num=float('inf'),
                      col_min_num=float('-inf'), col_max_num=float('inf'),
                      ck_row_num_ban=True, ck_col_num_ban=True, ban_num: list = None,
                      ck_row_standard=False, ck_col_standard=False, ck_standard_list: list = None,
                      com_col_row_mum=True, row_greater: bool = None, contain_equal=True):
        """
        文件详细内容检查，注意new_file与in_file为同一文件时，处理后将会替换旧文件，后续检查及程序应使用new_file替代in_file传参
        :param out_dir: 字符串，处理后对象输出目录，推荐os.path.join(args.outdir,"tmp/analysis")
        :param new_file: 字符串，处理后对象名，将保存到out_dir目录下,默认与原文件同名
        :param pre_check: 布尔值，是否调用pre_check_file_content进行预处理，默认True
        :param rm_space: 布尔值，是否去除元素前后空格，影响检查速度，默认True
        :param rm_blank: 布尔值，检查时是否移除该列元素前后空白，默认True
        :param fill_null: 布尔值，检查时是否将缺失数据统一替换为NA，默认True
        :param null_list: 字符串列表，检查时指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
        :param ck_header: 布尔值，是否检查标题行，初查，比较首行个数是否少于尾行，该功能已内置于pre_check_file_content，默认False
        :param ck_sep: 布尔值，是否检查分隔符规范，行数较多时，该步骤为耗时步骤，默认False
        :param sep_r: 字符串，纯文本读入的分隔符，含有与正则有关的字符应在字符串前加r,或将字符使用'\'转义,默认r'\t'
        :param ck_line_dup: 布尔值，是否检查行重复，默认False
        :param ck_row_num: 布尔值，是否检查行数（或行数范围），以首列行数为准，默认True
        :param ck_col_num: 布尔值，是否检查列数（或列数范围），以首行列数为准，默认True
        :param row_num_exp: 正整数，期望行数，None表示不检查，忽视ck_row_num
        :param col_num_exp: 正整数，期望列数，None表示不检查，忽视ck_col_num
        :param row_min_num_exp: 正整数，期望最小行数，优先级低于row_num_exp，默认0，与row_max_num_exp同时为None表示不检查，忽视ck_row_num
        :param col_min_num_exp: 正整数，期望最小列数，优先级低于col_num_exp，默认0，与col_max_num_exp同时为None表示不检查，忽视ck_row_num
        :param row_max_num_exp: 正整数，期望最大行数，优先级低于row_num_exp，默认无穷，与row_min_num_exp同时为None表示不检查，忽视ck_row_num
        :param col_max_num_exp: 正整数，期望最大列数，优先级低于col_num_exp，默认无穷，与col_min_num_exp同时为None表示不检查，忽视ck_row_num
        :param ck_row_base: 布尔值，是否检查行内容，基础检查，默认True
        :param ck_col_base: 布尔值，是否检查列内容，基础检查，默认True
        :param ck_row_list: 正整数/正整数列表，行内容基础检查，目标行号+，None或0表示全部行,-1表示去掉首行，默认1，即检查首行
        :param ck_col_list: 正整数/正整数列表，列内容基础检查，目标列号+，None或0表示全部列,-1表示去掉首列，默认1，即检查首列
        :param ck_row_length: 布尔值，基础检查，是否检查目标行固定长度，默认True，优先级高于范围检查
        :param ck_row_length_range: 布尔值，基础检查，是否检查目标行长度范围，默认True，ck_row_length=False时生效
        :param ck_row_dup: 布尔值，基础检查，是否检查目标行内重复，默认True
        :param ck_row_na: 布尔值，基础检查，是否检查目标行内缺失，默认True
        :param ck_row_ban: 布尔值，基础检查，是否检查目标行内禁用，默认True
        :param ck_col_length: 布尔值，基础检查，是否检查目标列固定长度，默认True，优先级高于范围检查
        :param ck_col_length_range: 布尔值，基础检查，是否检查目标列长度范围，默认True，ck_col_length=False时生效
        :param ck_col_dup: 布尔值，基础检查，是否检查目标列内重复，默认True
        :param ck_col_na: 布尔值，基础检查，是否检查目标列内缺失，默认True
        :param ck_col_ban: 布尔值，基础检查，是否检查目标列内禁用，默认True
        :param row_length: 整数，基础检查，期望目标行固定长度，None表示不检查，忽视ck_row_length
        :param row_min_len: 整数，基础检查，期望目标行长度下限，要求ck_row_length=False，默认0
        :param row_max_len: 整数，基础检查，期望目标行长度上限，要求ck_row_length=False，默认正无穷
        :param col_length: 整数，基础检查，期望目标列固定长度，None表示不检查，忽视ck_col_length
        :param col_min_len: 整数，基础检查，期望目标列长度下限，要求ck_col_length=False，默认0
        :param col_max_len: 整数，基础检查，期望目标列长度上限，要求ck_col_length=False，默认正无穷
        :param ban_list: 字符串/字符串列表，基础检查，禁用元素，行列通用，None表示不检查，忽视ck_row_ban/ck_col_ban
        :param na_list: 字符串/字符串列表，基础检查，定义为缺失数据的字符类型列表，行列通用，默认("", "NA", "N/A", "NULL")
        :param ck_row_fix: 布尔值，是否检查行固定内容，默认True
        :param ck_col_fix: 布尔值，是否检查列固定内容，默认True
        :param row_fix_no: 正整数，要检查固定内容的行号，默认1，即检查首行固定标题
        :param col_fix_no: 正整数，要检查固定内容的列号，默认1，即检查首列固定标题
        :param row_fix_content: 字符串/字符串列表，期望的检查行固定内容，None表示不检查，忽视ck_row_fix
        :param col_fix_content: 字符串/字符串列表，期望的检查列固定内容，None表示不检查，忽视ck_row_fix
        :param ck_row_type: 布尔值，是否检查行元素类型，默认False
        :param ck_col_type: 布尔值，是否检查列元素类型，默认False
        :param ck_row_type_list: 正整数/正整数列表，行元素类型检查行号+，None或0表示全部行,-1表示去掉首行，默认为None
        :param ck_col_type_list: 正整数/正整数列表，列元素类型检查列号+，None或0表示全部列,-1表示去掉首列，默认为None
        :param exp_type: 字符串，期望列表元素类型，限定为python支持的格式,如[int,float,str,bool,...]，默认"float"
        :param rm_first: 布尔值，是否去掉首个元素，仅针对行列元素类型检查及标准化检查有效，当文件有标题行时选True，默认False
        :param ck_row_num_range: 布尔值，行元素类型检查，是否检查数值范围，默认为False，只有数值类型才可以检查范围
        :param ck_col_num_range: 布尔值，行元素类型检查，是否检查数值范围，默认为False，只有数值类型才可以检查范围
        :param row_min_num: 浮点数，行元素类型检查，数值范围检查下限，默认负无穷
        :param row_max_num: 浮点数，行元素类型检查，数值范围检查上限，默认正无穷
        :param col_min_num: 浮点数，列元素类型检查，数值范围检查下限，默认负无穷
        :param col_max_num: 浮点数，列元素类型检查，数值范围检查上限，默认正无穷
        :param ck_row_num_ban: 布尔值，行元素类型检查，是否检查数值禁用，默认Ture
        :param ck_col_num_ban: 布尔值，列元素类型检查，是否检查数值禁用，默认Ture
        :param ban_num: 数值/数值列表，列元素类型检查，禁用数值，行列通用，None表示不检查，忽视ck_row_num_ban/ck_col_num_ban
        :param ck_row_standard: 布尔值，是否检查行元素能否进行标准化，注意标准化检查应在完成类型检查为数值后进行，默认False
        :param ck_col_standard: 布尔值，是否检查列元素能否进行标准化，注意标准化检查应在完成类型检查为数值后进行，默认False
        :param ck_standard_list: 正整数/正整数列表，标准化检查行/列号+，None表示全部行/列,-1表示去掉首行/列，行列通用，默认为None
        :param com_col_row_mum: 布尔值，是否比较的行列数维度关系，默认False
        :param row_greater: 布尔值，是否行数更多，None表示不检查，忽视com_col_row_mum
        :param contain_equal: 布尔值，比较的行列数维度关系时，是否含等号，作为row_greater参数补充,默认为True
        :return: 符合期望返回0，不符合返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            error_list = []
            if new_file is None:
                new_file = os.path.join(os.path.abspath(out_dir), self.__name)
            else:
                new_file = os.path.join(os.path.abspath(out_dir), os.path.basename(new_file))
                # new_file = os.path.join(os.path.dirname(os.path.abspath(in_file)), os.path.basename(new_file))  # 同路径
            if pre_check:
                err_msg = self.pre_check_content(out_dir=out_dir, new_file=new_file, encoding='utf-8',
                                                 rm_space=rm_space)
                if err_msg:
                    error_list.append(f"{self._e['输入']}{self.__name}:{err_msg}")
                    return error_list
            self.in_file = new_file  # 分隔符检查前，需确保使用去除空行及元素前后空白的新文件
            row_number = self.get_row_num()
            col_number = self.get_col_num()
            if ck_sep:
                for row in range(1, row_number + 1):
                    in_line = self.get_row_line(line_num=row)
                    err_msg = self.line_sep(in_line, sep_r=sep_r)
                    if err_msg:
                        error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['第']}{row}"
                                          f"{self._e['行']}{_wrap(err_msg, self_cut=False)}")
            if ck_header:
                in_list = self.get_row2list(row_no=1, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                tail_length = self.get_col_num()
                if len(in_list) < tail_length:
                    msg = f"{self.add_info}{self._e['输入']}{self.__name}{self._e['首行要求']}"
                    error_list.append(msg)
            if ck_line_dup:
                err_msg = self.line_dup()
                if err_msg:
                    error_list.append(f"{_wrap(err_msg, self_cut=False)}")
            if error_list:  # 维度检查前需确保分隔符正确
                return error_list
            if ck_row_num and row_num_exp is not None:
                in_list = self.get_col2list(col_no=1, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                err_msg = List(in_list=in_list, key=self._e['行']).length(exp_len=row_num_exp)
                if err_msg:
                    error_list.append(
                        f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行数有误']}{_wrap(err_msg, self_cut=False)}")
            if ck_col_num and col_num_exp is not None:
                in_list = self.get_row2list(row_no=1, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                err_msg = List(in_list=in_list, key=self._e['列']).length(exp_len=col_num_exp)
                if err_msg:
                    err_msg += f"{self._e['表格检查']}"
                    error_list.append(
                        f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列数有误']}{_wrap(err_msg, self_cut=False)}")
            if ck_row_num and row_num_exp is None and (row_min_num_exp or row_max_num_exp) is not None:
                if row_min_num_exp is None:
                    row_min_num_exp = 1
                if row_max_num_exp is None:
                    row_max_num_exp = float('inf')
                in_list = self.get_col2list(col_no=1, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                err_msg = List(in_list=in_list, key=self._e['行'], no_log=self.no_log, lang=self.lang).length(
                    min_len=row_min_num_exp, max_len=row_max_num_exp)
                if err_msg:
                    error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行数范围有误']}"
                                      f"{_wrap(err_msg, self_cut=False)}")
            if ck_col_num and col_num_exp is None and (col_min_num_exp or col_max_num_exp) is not None:
                if col_min_num_exp is None:
                    col_min_num_exp = 1
                if col_max_num_exp is None:
                    col_max_num_exp = float('inf')
                in_list = self.get_row2list(row_no=1, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                err_msg = List(in_list=in_list, key=self._e['列'], no_log=self.no_log, lang=self.lang).length(
                    min_len=col_min_num_exp, max_len=col_max_num_exp)
                if err_msg:
                    err_msg += f"{self._e['表格检查']}"
                    error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列数范围有误']}"
                                      f"{_wrap(err_msg, self_cut=False)}")
            if error_list:  # 行列内容检查前需确保维度正确
                return error_list
            if ck_row_base:
                if ck_row_list == -1:
                    ck_row_list = range(2, row_number + 1)
                elif ck_row_list is None or ck_row_list == 0:
                    ck_row_list = range(1, row_number + 1)
                if isinstance(ck_row_list, int):
                    ck_row_list = [ck_row_list, ]
                for row in ck_row_list:
                    in_list = self.get_row2list(row_no=row, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                    if ck_row_length and row_length is not None:
                        err_msg = List(in_list=in_list, no_log=True).length(exp_len=row_length)
                        if err_msg:
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}"
                                              f"{_wrap(err_msg, self_cut=False)}")
                    elif not ck_row_length and ck_row_length_range:
                        err_msg = List(in_list=in_list, no_log=True).range(min_len=row_min_len, max_len=row_max_len)
                        if err_msg:
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}"
                                              f"{_wrap(err_msg, self_cut=False)}")
                    if ck_row_dup:
                        err_msg = List(in_list=in_list, no_log=True).dup()
                        if err_msg:
                            error_list.append(
                                f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}{self._e['有重复']}"
                                f"{_wrap(err_msg, self_cut=False)}{self._e['要无重']}")
                    if ck_row_ban and ban_list is not None:
                        err_msg = List(in_list=in_list, no_log=True).ban(ban_list=ban_list)
                        if err_msg:
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}"
                                              f"{self._e['有非法']}{_wrap(err_msg, self_cut=False)}")
                    if ck_row_na:
                        err_msg = List(in_list=in_list, no_log=True).na(na_list=na_list)
                        if err_msg:
                            err_msg += f"{self._e['表格检查']}"
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}"
                                              f"{_wrap(err_msg, self_cut=False)}")
            if ck_col_base:
                if ck_col_list == -1:
                    ck_col_list = range(2, col_number + 1)
                elif ck_col_list is None or ck_col_list == 0:
                    ck_col_list = range(1, col_number + 1)
                if isinstance(ck_col_list, int):
                    ck_col_list = [ck_col_list, ]
                for col in ck_col_list:
                    in_list = self.get_col2list(col_no=col, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                    if ck_col_length and col_length is not None:
                        err_msg = List(in_list=in_list, no_log=True).length(exp_len=col_length)
                        if err_msg:
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                              f"{_wrap(err_msg, self_cut=False)}")
                    elif not ck_col_length and ck_col_length_range:
                        err_msg = List(in_list=in_list, no_log=True).range(min_len=col_min_len, max_len=col_max_len)
                        if err_msg:
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                              f"{_wrap(err_msg, self_cut=False)}")
                    if ck_col_dup:
                        err_msg = List(in_list=in_list, no_log=True).dup()
                        if err_msg:
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                              f"{self._e['有重复']}{_wrap(err_msg, self_cut=False)}{self._e['要无重']}")
                    if ck_col_ban and ban_list is not None:
                        err_msg = List(in_list=in_list, no_log=True).ban(ban_list=ban_list)
                        if err_msg:
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                              f"{self._e['有非法']}{_wrap(err_msg, self_cut=False)}")
                    if ck_col_na:
                        err_msg = List(in_list=in_list, no_log=True).na(na_list=na_list)
                        if err_msg:
                            err_msg += f"{self._e['表格检查']}"
                            error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                              f"{_wrap(err_msg, self_cut=False)}")
            if ck_row_fix and row_fix_content is not None:
                in_list = self.get_row2list(
                    row_no=row_fix_no, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                if isinstance(row_fix_content, str):
                    row_fix_content = [row_fix_content, ]
                if in_list != list(row_fix_content):
                    in_title = ",".join(map(lambda x: str(x), in_list))
                    allowed_title = ",".join(map(lambda x: str(x), row_fix_content))
                    in_title = in_title[:45] + " ... " if len(in_title) > 50 else in_title
                    err_msg = f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row_fix_no}" \
                              f"{self._e['必须为']}{_wrap(allowed_title, self_cut=False)},\n" \
                              f"{self._e['实际为']}{in_title}{self._e['请检查']}"
                    error_list.append(err_msg)
            if ck_col_fix and col_fix_content is not None:
                in_list = self.get_col2list(
                    col_no=col_fix_no, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                if isinstance(col_fix_content, str):
                    col_fix_content = [col_fix_content, ]
                if in_list != list(col_fix_content):
                    in_title = ",".join(map(lambda x: str(x), in_list))
                    allowed_title = ",".join(map(lambda x: str(x), col_fix_content))
                    in_title = in_title[:45] + " ... " if len(in_title) > 50 else in_title
                    err_msg = f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col_fix_no}" \
                              f"{self._e['必须为']}{_wrap(allowed_title, self_cut=False)},\n" \
                              f"{self._e['实际为']}{in_title}{self._e['请检查']}"
                    error_list.append(err_msg)
            row_flag = []
            if ck_row_type:
                if ck_row_type_list == -1:
                    ck_row_type_list = list(range(2, row_number + 1))
                elif ck_row_type_list is None or ck_row_type_list == 0:
                    ck_row_type_list = list(range(1, row_number + 1))
                if isinstance(ck_row_type_list, int):
                    ck_row_type_list = [ck_row_type_list, ]
                for row in ck_row_type_list:
                    in_list = self.get_row2list(row_no=row, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                    msg = List(in_list=in_list, rm_first=rm_first, no_log=True).type(exp_type=exp_type)
                    if isinstance(msg, str):
                        error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}"
                                          f"{_wrap(msg, self_cut=False)}")
                    else:
                        if exp_type in ['float', 'int']:
                            row_flag.append(1)
                        if ck_row_num_range:
                            err_msg = List(in_list=msg, no_log=True).num_range(min_num=row_min_num, max_num=row_max_num)
                            if err_msg:
                                error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}"
                                                  f"{_wrap(err_msg, self_cut=False)}")
                        if ck_row_num_ban and ban_num is not None:
                            err_msg = List(in_list=msg, no_log=True).num_ban(ban_num=ban_num)
                            if err_msg:
                                error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}"
                                                  f"{_wrap(err_msg, self_cut=False)}")
            col_flag = []
            if ck_col_type:
                if ck_col_type_list == -1:
                    ck_col_type_list = list(range(2, col_number + 1))
                elif ck_col_type_list is None or ck_col_type_list == 0:
                    ck_col_type_list = list(range(1, col_number + 1))
                if isinstance(ck_col_type_list, int):
                    ck_col_type_list = [ck_col_type_list, ]
                for col in ck_col_type_list:
                    in_list = self.get_col2list(col_no=col, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                    msg = List(in_list=in_list, rm_first=rm_first, no_log=True).type(exp_type=exp_type)
                    if isinstance(msg, str):
                        error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                          f"{_wrap(msg, self_cut=False)}")
                    else:
                        if exp_type in ['float', 'int']:
                            col_flag.append(1)
                        if ck_col_num_range:
                            err_msg = List(in_list=msg, no_log=True).num_range(min_num=col_min_num, max_num=col_max_num)
                            if err_msg:
                                error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                                  f"{_wrap(err_msg, self_cut=False)}")
                        if ck_col_num_ban and ban_num is not None:
                            err_msg = List(in_list=msg, no_log=True).num_ban(ban_num=ban_num)
                            if err_msg:
                                error_list.append(f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}"
                                                  f"{_wrap(err_msg, self_cut=False)}")
            if row_flag and ck_row_standard:
                if ck_standard_list == -1:
                    ck_standard_list = list(range(2, row_number + 1))
                elif ck_standard_list is None:
                    ck_standard_list = list(range(1, row_number + 1))
                if isinstance(ck_standard_list, int):
                    ck_standard_list = [ck_standard_list, ]
                if set(ck_standard_list).issubset(set(ck_row_type_list)):
                    for row in ck_standard_list:
                        in_list = self.get_row2list(
                            row_no=row, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                        msg = List(in_list=in_list, rm_first=rm_first, no_log=True).factor(exp_num=1)
                        if not msg:
                            error_list.append(
                                f"{self.add_info}{self._e['输入']}{self.__name}{self._e['行号']}{row}{self._e['行标准化要求']}")
            if col_flag and ck_col_standard:
                if ck_standard_list == -1:
                    ck_standard_list = list(range(2, col_number + 1))
                elif ck_standard_list is None:
                    ck_standard_list = list(range(1, col_number + 1))
                if isinstance(ck_standard_list, int):
                    ck_standard_list = [ck_standard_list, ]
                if set(ck_standard_list).issubset(set(ck_col_type_list)):
                    for col in ck_standard_list:
                        in_list = self.get_col2list(
                            col_no=col, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                        print(in_list)
                        msg = List(in_list=in_list, rm_first=rm_first, no_log=True).factor(exp_num=1)
                        if not msg:
                            error_list.append(
                                f"{self.add_info}{self._e['输入']}{self.__name}{self._e['列号']}{col}{self._e['列标准化要求']}")
            if com_col_row_mum and row_greater is not None:
                err_msg = self.com_row_col_num(row_greater=row_greater, contain_equal=contain_equal)
                if err_msg:
                    error_list.append(f"{self._e['输入']}{self.__name}{_wrap(err_msg, self_cut=False)}")
            if len(error_list) == 0:
                return 0
            else:
                return error_list
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}检查文件详细内容时出错", ]

    def compare_line(self, in_file2,
                     file1_dim="row", file2_dim="row", file1_no=1, file2_no=1,
                     order_strict=False, rm_first=False, ck_1_in_2=False,
                     rm_blank=True, fill_null=False, null_list=None, key='样本'):
        """
        对比两个文件某一行/列数据的差异
        :param in_file2: 字符串，检查对象2,例如："D:\b.txt"
        :param file1_dim: 部分整数/字符串，文件1检查维度【取行/列】，可选[1, '1', 'row', '行'][2, '2', 'col', 'column', '列']
        :param file2_dim: 部分整数/字符串，文件2检查维度【取行/列】，可选[1, '1', 'row', '行'][2, '2', 'col', 'column', '列']
        :param file1_no: 正整数，检查对象1要检查的行/列号，默认1
        :param file2_no: 正整数，检查对象2要检查的行/列号，默认1
        :param order_strict: 布尔值，是否严格顺序比较，默认False，即不考虑元素顺序
        :param rm_first: 布尔值，是否移除首个元素，默认False
        :param ck_1_in_2: 布尔值，是否检查list1是否包含于list2，默认False，即仅寻找互斥元素
        :param rm_blank: 布尔值，是否移除该列元素前后空白，默认True
        :param fill_null: 布尔值，是否将缺失数据统一替换为NA，默认True
        :param null_list: 字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
        :param key: 字符串，关键字信息，默认'样本'
        :return: 符合期望返回0，不符合返回报错信息列表
        print(__name__, self._c, _name()) if not self.no_log else 1
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            row_options = [1, "1", "row", "行"]
            col_options = [2, "2", "col", "column", "列"]
            dim_options = row_options + col_options
            if file1_dim not in dim_options:
                print(f'文件1检查维度设置错误，重置为取行，仅接受{dim_options}')
                file1_dim = 1
            if file2_dim not in dim_options:
                print(f'文件2检查维度设置错误，重置为取行，仅接受{dim_options}')
                file2_dim = 1
            if not os.path.isfile(in_file2):
                return [f"{self.add_info}{self._e['比较文件出错']}{in_file2}{self._e['非文件']}", ]
            dim1 = f"{self._e['行号']}" if file1_dim in row_options else f"{self._e['列号']}"
            dim2 = f"{self._e['行号']}" if file2_dim in row_options else f"{self._e['列号']}"
            file2_name = os.path.basename(in_file2)
            if file1_dim in row_options:
                in_list1 = self.get_row2list(row_no=file1_no, rm_blank=rm_blank,
                                             fill_null=fill_null, null_list=null_list)
            else:
                in_list1 = self.get_col2list(col_no=file1_no, rm_blank=rm_blank,
                                             fill_null=fill_null, null_list=null_list)
            if file2_dim in row_options:
                in_list2 = _row2list(file=in_file2, sep=self.sep, row_no=file2_no, rm_blank=rm_blank,
                                     fill_null=fill_null, null_list=null_list)
            else:
                in_list2 = _col2list(file=in_file2, sep=self.sep, col_no=file2_no, rm_blank=rm_blank,
                                     fill_null=fill_null, null_list=null_list)
            msg = List(in_list=in_list1, key=key, rm_first=rm_first, no_log=self.no_log, lang=self.lang).compare(
                list2=in_list2, order_strict=order_strict, ck_1_in_2=ck_1_in_2)
            if msg != 0:
                return [f'{self.add_info}{self.__name}{dim1}{file1_no} <-> {file2_name}{dim2}{file2_no}:{msg}', ]
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['compare_line']}", ]

    com_line = compare_line

    def str_in_line(self, in_str, ck_row=True, ck_col=True, row_no: int = None, col_no: int = None, rm_blank=True,
                    fill_null=False, null_list=None):
        """
        检查（参数等）字符串/字符串列表是否（全部）包含在文件某行中
        :param in_str: 字符串/字符串列表，检查对象字符串
        :param ck_row: 布尔值，是否检查某行，默认True
        :param ck_col: 布尔值，是否检查某列，默认True
        :param row_no: 正整数，检查行行号，None表示不检查行，忽视ck_row
        :param col_no: 正整数，检查列列号，None表示不检查列，忽视ck_col
        :param rm_blank: 布尔值，移除该列元素前后空白，默认True
        :param fill_null: 布尔值，将缺失数据统一替换为NA，默认True
        :param null_list: 字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
        :return: 符合期望返回0，不符合返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if isinstance(in_str, str):
                in_str = [in_str, ]
            error_list = []
            if ck_row and row_no is not None:
                in_list = self.get_row2list(row_no=row_no, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                in_list = list(map(lambda x: str(x), in_list))
                in_str = list(map(lambda x: str(x), in_str))
                str_item = set(in_str).difference(set(in_list))
                if str_item:
                    error_list.append(
                        f"{self.add_info}{self.__name}{self._e['行号']}{row_no}{self._e['不含']}"
                        f"{_wrap(_join_str(str_item))}{self._e['元素']}")
            if ck_col and col_no is not None:
                in_list = self.get_col2list(col_no=col_no, rm_blank=rm_blank, fill_null=fill_null, null_list=null_list)
                in_list = list(map(lambda x: str(x), in_list))
                in_str = list(map(lambda x: str(x), in_str))
                str_item = set(in_str).difference(set(in_list))
                if str_item:
                    error_list.append(
                        f"{self.add_info}{self.__name}{self._e['列号']}{col_no}{self._e['不含']}"
                        f"{_wrap(_join_str(str_item))}{self._e['元素']}")
            if len(error_list) != 0:
                return error_list
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['str_in_line']}", ]


@_pre_class
class List(object):
    """check List"""

    def __init__(self, in_list: list, key="元素", rm_first=False, add_info="", no_log=False, lang=LANG):
        """
        列表类型数据检查
        check tools for List
        :param in_list: 列表，检查对象
        :param key: 字符串，列表元素展示通名，关键字
        :param rm_first: 布尔值，高优先级，是否去掉首个元素，当文件有标题行时可选True，默认False
        :param add_info: 字符串，附加信息
        :param no_log: 不打印调用及报错信息，默认为False
        :param lang: 字符串，选择报错语言，可选["CN", "EN"]，默认CN
        """
        fix_list = [in_list, ] if isinstance(in_list, str) else list(in_list)
        fix_list = fix_list[1:] if rm_first else fix_list
        self.fix_list = fix_list
        self.key = key
        self.add_info = add_info
        self.no_log = no_log
        self.lang = lang
        self._c = self.__class__.__name__  # 类名
        self._e = self.lang_dic[self.lang][self._c]  # 报错字典初定位
        self.in_list = None  # 可变值方法实际操作列表
        self.na_add_info = add_info  # na实际使用附加信息 缓冲
        self.ban_add_info = add_info  # ban实际使用附加信息 缓冲
        self.factor_buff = ""  # factor实际检查使用列表 缓冲

    def __repr__(self):
        return 'List(in：{0.fix_list!r}, key：{0.key!r}, add：{0.add_info!r}, ' \
               'quiet：{0.no_log!r}, lang：{0.lang!r})'.format(self)

    def __str__(self):
        return '(in：{0.fix_list!s}, key：{0.key!r}, add：{0.add_info!s}, ' \
               'quiet：{0.no_log!s}, lang：{0.lang!s})'.format(self)

    def length(self, exp_len: int = None, min_len=0, max_len: int = float('inf')):
        """
        检查列表长度是否为固定长度/在范围内，固定长度检查优先级高于范围内检查
        :param exp_len: 整数，期望固定长度，优先级高于范围内检查，None表示执行范围内检查
        :param min_len: 整数，最小长度，length=None时使用，默认0
        :param max_len: 整数，最大长度，length=None时使用，默认正无穷
        :return: 为固定长度/在范围内返回0，否则返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        list_len = len(self.factor_buff) if self.factor_buff else len(self.fix_list)  # 判断是否由factor方法调用
        self.factor_buff = ""  # factor方法缓冲列表复原
        try:
            if exp_len is None:
                if max_len >= list_len >= min_len:
                    return 0
                else:
                    max_len = f"{self._e['无穷']}" if max_len == float('inf') else max_len
                    return f"{self.add_info}{self._e['有']}{list_len}{self._e['个']}{self.key}" \
                           f"{self._e['要求数量']}[{min_len},{max_len}]"
            else:
                if list_len != exp_len:
                    return f"{self.add_info}{self._e['有']}{list_len}{self._e['个']}{self.key}" \
                           f"{self._e['应为']}{exp_len}{self._e['个']}{self.key}"
                else:
                    return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['length']}"

    def range(self, min_len=0, max_len: int = float('inf')):
        """
        检查列表长度是否在范围内
        :param min_len: 整数，最小长度，默认0
        :param max_len: 整数，最大长度，默认正无穷
        :return: 范围内返回0，范围外返回字符串报错信息
        """
        return self.length(min_len=min_len, max_len=max_len)

    def dup(self):
        """
        检查列表中的重复元素
        :return: 无重复0，有重复返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            self.in_list = list(map(lambda x: str(x).strip(), self.fix_list))
            if len(self.in_list) == len(set(self.in_list)):
                return 0
            list_count = dict(Counter(self.in_list))
            dup_item = [key for key, value in list_count.items() if value > 1]
            if not dup_item:
                return 0
            else:
                return f"{self.add_info}{self._e['重复']}{self.key}:{_wrap(_join_str(dup_item))}{self._e['检查']}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['dup']}"

    def ban(self, ban_list: list = None):
        """
        检查列表中的禁用元素
        :param ban_list: 字符串/字符串列表，禁用元素，默认[]，即无禁用
        :return: 无禁用返回0，有禁用返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        self.ban_add_info = self.na_add_info if f"{self._e['空缺']}" in self.na_add_info else self.add_info
        self.na_add_info = self.add_info
        try:
            if isinstance(ban_list, str):
                ban_list = [ban_list, ]
            if ban_list is None:
                ban_list = []
            self.in_list = list(map(lambda x: str(x), self.fix_list))
            ban_list = list(map(lambda x: str(x), ban_list))
            ban_item = set(self.in_list).intersection(set(ban_list))
            if ban_item:
                return f"{self.ban_add_info}{self.key}:{_join_str(ban_item)}{self._e['检查']}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['ban']}"

    def na(self, na_list: list = None):
        """
        检查列表中是否包含缺失数据
        :param na_list: 字符串/字符串列表，定义为缺失数据的字符类型列表，默认("", "NA", "N/A", "NULL")
        :return: 无缺失返回0，有缺失返回字符串报错信息
        """
        self.na_add_info = self.add_info + f"{self._e['空缺']}"
        try:
            if isinstance(na_list, str):
                na_list = [na_list, ]
            if na_list is None:
                na_list = list(NONE_LIST)
            return self.ban(ban_list=na_list)
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.na_add_info}{self._e['na']}"

    def format(self, re_obj=None, re_ban_body=None, ck_head=True, re_ban_head=None,
               ck_tail=False, re_ban_tail=None):
        """
        列表字符串正则范围内检查（默认以字母/数字开头，仅包含字母、数字、点和中划线和下划线）
        :param re_obj: re.compile对象，允许的正则格式编译，默认re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._-])*$')
        :param re_ban_body: re.compile对象，错误的主体字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9._-]")
        :param ck_head: 布尔值，是否检查字符串首个字符，默认True
        :param re_ban_head: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"^[^A-Za-z0-9]")
        :param ck_tail: 布尔值，是否检查字符串末尾字符，默认False
        :param re_ban_tail: re.compile对象，错误的结尾字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9]$")
        :return: 范围内返回0，范围外返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if re_obj is None:
                re_obj = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._-])*$')
                if re_ban_body is None:
                    re_ban_body = re.compile(r"[^A-Za-z0-9._-]")
                if ck_head and re_ban_head is None:
                    re_ban_head = re.compile(r"^[^A-Za-z0-9]")
                if ck_tail and re_ban_tail is None:
                    re_ban_tail = re.compile(r"[^A-Za-z0-9]$")
            error_item = []
            for i in self.fix_list:
                err_msg = Str(in_str=i, no_log=True, lang=self.lang).format(
                    re_obj=re_obj, re_ban_body=re_ban_body, ck_head=ck_head, re_ban_head=re_ban_head,
                    re_ban_tail=re_ban_tail)
                if err_msg:
                    error_item.append(i)
            if error_item:
                return f"{self.add_info}{self._e['不合规']}{self.key}{_wrap(_join_str(error_item))}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['format']}"

    def factor(self, exp_num=None, min_num=1, max_num: int = float('inf')):
        """
        列表因子（非重复元素）个数检查
        :param exp_num: 整数，期望因子个数，优先级高于范围内检查，None表示执行范围内检查
        :param min_num: 整数，最小个数，exp_num=None时使用，默认1
        :param max_num: 整数，最小个数，exp_num=None时使用，默认正无穷
        :return: 范围内返回0，范围外返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            self.factor_buff = list(set(self.fix_list))
            msg = self.length(exp_len=exp_num, min_len=min_num, max_len=max_num)
            if msg:
                return f"{self.add_info}{msg}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['factor']}"

    factor_num = class_num = group_num = factor

    def type(self, exp_type='float'):
        """
        检查列表元素类型，并转换期望元素类型的新列表
        :param exp_type: 字符串，期望列表元素类型，限定为python支持的格式,如[int,float,str,bool,...]，默认"float"
        :return: 正常返回期望类型的新列表，异常返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            return list(map(eval(exp_type.lower()), self.fix_list))
        except ValueError as e:
            if exp_type.lower() == "float":
                exp_type = f"{self._e['数值']}"
            elif exp_type.lower() == "int":
                exp_type = f"{self._e['整数']}"
            else:
                print(f'Error:The expected list element type is set incorrectly')
            return f"{self.add_info}{self._e['非']}{exp_type}{self._e['类值']}" + str(e).split(':')[-1]
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['type']}"

    def num_range(self, min_num=float('-inf'), max_num=float('inf')):
        """
        检查数值列表元素数值是否在范围内
        :param min_num: 浮点数，数值下限，默认负无穷
        :param max_num: 浮点数，数值上限，默认正无穷
        :return: 正常返回0，异常返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            err_list = []
            for i in range(1, len(self.fix_list) + 1):
                msg = Num(in_num=float(self.fix_list[i - 1]), add_info=f'第{i}个数值：', no_log=True,
                          lang=self.lang).range(min_num=min_num, max_num=max_num)
                if msg:
                    err_list.append(i)
            if err_list:
                min_num = f"{self._e['负无穷']}" if min_num == float('-inf') else min_num
                max_num = f"{self._e['正无穷']}" if max_num == float('inf') else max_num
                index = self._e['第']
                return f"{self.add_info}{self._e['下限']}{min_num}{self._e['上限']}{max_num}{self._e['检测到']}" \
                       f"{_wrap(index + _join_str(err_list))}{self._e['个']}{self.key}{self._e['超限']}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['num_range']}"

    def num_ban(self, ban_num: list = None):
        """
        检查数值列表元素数值有无禁用值
        :param ban_num: 数值/数值列表，禁用数值，None表示无禁用限制
        :return: 正常返回0，异常返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            err_list = []
            if isinstance(ban_num, float) or isinstance(ban_num, int):
                ban_num = [ban_num, ]
            for i in range(1, len(self.fix_list) + 1):
                msg = Num(in_num=float(self.fix_list[i - 1]), add_info="", no_log=True, lang=self.lang).ban(
                    ban_num=ban_num)
                if msg:
                    err_list.append(i)
            if err_list:
                index = self._e['第']
                return f"{self.add_info}{self._e['禁用']}{_join_str(ban_num)}{self._e['检测到']}" \
                       f"{_wrap(index + _join_str(err_list), self_len=160)}{self._e['个']}{self.key}{self._e['为禁用']}"
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['num_ban']}"

    def compare(self, list2: list, order_strict=False, ck_1_in_2=False):
        """
        比较两个列表元素是否相同
        :param list2: 列表，第二个比较对象
        :param order_strict: 布尔值，是否严格顺序比较，默认False,即不考虑元素顺序
        :param ck_1_in_2: 布尔值，是否检查list1是否包含于list2，默认False，即仅寻找互斥元素
        :return: 相同返回0，不同返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            if order_strict:
                other = ''
                err = []
                if ck_1_in_2 and len(self.fix_list) > len(list2):
                    other += f"{self._e['存在多的']}{self.key}{self._e['且']}"
                elif not ck_1_in_2 and len(self.fix_list) != len(list2):
                    other += f"{self._e['不等']}"
                n = min(len(self.fix_list), len(list2))
                for i in range(1, n + 1):
                    if self.fix_list[i - 1] != list2[i - 1]:
                        # err.append(i)  # 元素位置
                        err.append(self.fix_list[i - 1])  # 元素名
                if len(err) != 0:
                    # msg = f"{self.add_info}发现不同{self.key}，分别为第{_join_str(err)}个{other} "  # 元素位置
                    msg = f"{self.add_info}{other}{self._e['发现不同']}{self.key}{self._e['为']}{_wrap(_join_str(err))} "
                    return msg
                else:
                    return 0
            else:
                set1 = set(self.fix_list)
                set2 = set(list2)
                diff_items = list(set1.symmetric_difference(set2))
                if not diff_items:
                    return 0
                diff1 = list(set1.difference(set2))
                if ck_1_in_2 and diff1:
                    return f"{self.add_info}{self._e['发现多的']}{self.key}{self._e['为']}{_wrap(_join_str(diff1))}"
                elif not ck_1_in_2:
                    diff2 = list(set2.difference(set1))
                    index = self._e['和']
                    return f"{self.add_info}{self._e['发现不同']}{self.key}{self._e['为']}{_wrap(_join_str(diff1))}\n" \
                           f"{_wrap(index + _join_str(diff2))}"
                else:
                    return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['compare']}"


@_pre_class
class Tool(object):
    """Start check / outfit / End check / make result or give err_log"""

    def __init__(self, add_info="", no_log=False, lang=LANG):
        """
        检查模块常规工作及工具
        Start check / outfit / End check / make result or give err_log
        :param add_info: 字符串，附加信息
        :param no_log: 不打印调用及报错信息，默认为False
        :param lang: 字符串，选择报错语言，可选["CN", "EN"]，默认CN
        """
        self.add_info = add_info
        self.no_log = no_log
        self.lang = lang
        self._c = self.__class__.__name__  # 类名
        self._e = self.lang_dic[self.lang][self._c]  # 报错字典初定位

    def __repr__(self):
        return 'Tool(add：{0.add_info!r}, quiet：{0.no_log!r}, lang：{0.lang!r})'.format(self)

    def __str__(self):
        return '(add：{0.add_info!s},  quiet：{0.no_log!s}, lang：{0.lang!s})'.format(self)

    def del_all(self, path, self_contain=False):
        """
        删除指定目录下所有内容（包含文件及文件夹，默认不包含自身）
        :param path: 字符串，指定目录，推荐绝对路径
        :param self_contain: 布尔值，是否删除path自身，默认False
        :return: 删除成功无返回，删除失败返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            path = _path_pre_proc(path)
            if self_contain:
                shutil.rmtree(path, True)
            else:
                items = os.listdir(path)
                for i in items:
                    i_item = os.path.join(path, i)
                    if os.path.isdir(i_item):
                        # del_file(i_item)  # 递归式
                        shutil.rmtree(i_item, True)
                    else:
                        os.remove(i_item)
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['del_all']}{path}"

    dir_del_all = dir_del = del_dir = del_all

    def make_dir(self, path, del_old=True):
        """
        创建目录(注意：该函数默认会删除已存在目录下所有内容)
        :param path: 字符串，创建的文件夹名称，推荐绝对路径
        :param del_old: 布尔值，是否删除已存在目录及其中文件（夹）并重建目录，默认True
        :return: 创建成功无返回，创建失败返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            path = _path_pre_proc(path)
            if os.path.exists(path):
                if del_old:
                    self.del_all(path)
            else:
                os.makedirs(path)
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['make_dir']}{path}"

    def copy_file(self, in_file, path, new_file=None):
        """
        复制文件到目标路径下
        :param in_file: 字符串，复制文件，要复制的文件名称
        :param path: 字符串，复制文件的目标文件夹名称，推荐绝对路径，如路径不存在，将创建该路径
        :param new_file: 字符串，目标文件，复制后的文件名称，None表示与原文件同名
        :return: 成功返回0，失败返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            in_file = os.path.abspath(in_file)
            if os.path.isfile(in_file):
                if new_file is None:
                    new_file = os.path.basename(in_file)
                new_file = os.path.join(os.path.abspath(path), os.path.basename(new_file))
                if in_file == new_file:
                    return f"{self.add_info}{self._e['同文件']}{in_file}"
                if not os.path.exists(path):
                    os.makedirs(path)
                shutil.copyfile(in_file, new_file)
                return 0
            else:
                return f"{self.add_info}{self._e['非文件']}{in_file}"
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['copy_file']}"

    def make_cloud_dir(self, path, more=True, more_dir: list = None, del_old=True):
        """
        创建云平台 v2.0 结果目录树
        :param path: 字符串，创建结果目录树的路径（tmp父级目录），推荐绝对路径
        :param more: 布尔值，是否需要额外创建分析分析文件夹,默认True
        :param more_dir: 字符串/字符串列表，创建额外分析文件夹的名称，默认创建 analysis 文件夹
        :param del_old: 布尔值，是否删除已存在目录及其中文件（夹）并重建目录，默认True，不推荐修改该默认参数
        :return: 创建成功无返回，创建失败返回字符串报错信息
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            path = _path_pre_proc(path)
            abs_path = os.path.abspath(path)
            for i in ["tmp", "cloud_result", "cloud_error", "cloud_svg"]:
                new_dir = os.path.join(abs_path, "tmp") if i == "tmp" else os.path.join(abs_path, "tmp", i)
                err_msg = self.make_dir(new_dir, del_old=del_old)
                if err_msg:
                    return f'{self.add_info}{err_msg}'
            if more:
                if more_dir is None:
                    more_dir = 'analysis'
                if isinstance(more_dir, str):
                    more_dir = [more_dir, ]
                for i_dir in more_dir:
                    ana_dir = os.path.join(abs_path, "tmp", i_dir)
                    err_msg = self.make_dir(ana_dir, del_old=del_old)
                    if err_msg:
                        return f'{self.add_info}{err_msg}'
        except Exception as e:
            print(e) if not self.no_log else 1
            return f"{self.add_info}{self._e['make_cloud_dir']}"

    def check_dir_item(self, path, exp_item: list = None, ck_null=True):
        """
        文件夹目录内容检查(存在，空文件)
        :param path: 字符串，检查目录路径，推荐绝对路径
        :param exp_item: 字符串/字符串列表，期望存在的文件列表，None表示将path文件夹内容全部检查
        :param ck_null: 布尔值，是否检查空文件，默认True
        :return: 符合期望返回0，不符合期望返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            path = _path_pre_proc(path)
            if exp_item is None:
                exp_item = os.listdir(path)
            if isinstance(exp_item, str):
                exp_item = [exp_item, ]
            no_item = []  # 不存在文件
            have_item = []
            null_item = []  # 空文件
            for i_exp in exp_item:
                if i_exp not in os.listdir(path):
                    no_item.append(i_exp)
                else:
                    have_item.append(i_exp)
                    if ck_null:
                        msg = File(os.path.join(path, i_exp), no_log=self.no_log, lang=self.lang).null()
                        if msg:
                            null_item.append(i_exp)
            if len(have_item) == 0:
                return [f"{self.add_info}{self._e['无结果']}", ]
            elif len(no_item) != 0 and len(null_item) == 0:
                return [f"{self.add_info}{self._e['结果不全']}{_wrap(_join_str(no_item))}{self._e['检查']}", ]
            elif len(no_item) != 0 and len(null_item) != 0:
                return [f"{self.add_info}{self._e['结果不全']}{_wrap(_join_str(no_item))}"
                        f"{self._e['有空文件']}{_wrap(_join_str(null_item))}", ]
            elif len(no_item) == 0 and len(null_item) != 0:
                return [f"{self.add_info}{self._e['空文件']}{_wrap(_join_str(null_item))}", ]
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['check_dir_item']}", ]

    def make_result(self, path, out_dir, exp_item=None, out2zip='result.zip', out2json: str = None):
        """
        创建结果文件压缩包并将压缩包(及json)文件移至云平台2.0要求存储目录
        :param path: 字符串，数据分析结果临时储存目录，推荐绝对路径
        :param out_dir: 字符串，结果存储文件夹(tmp文件夹的父级目录)
        :param exp_item: 字符串/字符串列表，path目录中要打包进压缩包的结果文件[夹](文件夹将会被遍历，文件含后缀)，
            None表示将path文件夹内容全部打包
        :param out2zip: 字符串，结果文件压缩包名称(含后缀)，V2.0要求固定为 result.zip，不建议修改此项
        :param out2json: 字符串，path目录下json结果文件名称(含后缀),None表示无json文件需要转移
        :return: 正常返回0，错误返回报错信息列表
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        try:
            path = _path_pre_proc(path)
            path = os.path.abspath(path)
            if exp_item is None:
                exp_item = os.listdir(path)
            if isinstance(exp_item, str):
                exp_item = [exp_item, ]
            if out2json and out2json in exp_item:
                exp_item.remove(out2json)
            base_name = os.path.basename(out2zip)
            out2zip = os.path.join(path, base_name)
            error_list = []
            try:
                old_dir = os.getcwd()
                os.chdir(path)
                zip1 = ZipFile(out2zip, "w")
                for file_i in exp_item:
                    if os.path.isdir(file_i):
                        for folder, sub_folder, files in os.walk(file_i):
                            zip1.write(folder)
                            for i in files:
                                zip1.write(os.path.join(folder, i))
                    else:
                        zip1.write(file_i)
                zip1.close()
                os.chdir(old_dir)
            except Exception as e:
                print(e) if not self.no_log else 1
                err_msg = f"{self.add_info}{self._e['压缩报错']}"
                error_list.append(err_msg)
            try:
                res_file = os.path.join(out_dir, 'tmp/cloud_result', base_name)
                shutil.copyfile(out2zip, res_file)
            except Exception as e:
                print(e) if not self.no_log else 1
                err_msg = f"{self.add_info}{self._e['复制报错']}"
                error_list.append(err_msg)
            if out2json:
                base_name = os.path.basename(out2json)
                out2json = os.path.join(path, base_name)
                try:
                    res_file = os.path.join(out_dir, 'tmp/cloud_svg', base_name)
                    shutil.copyfile(out2json, res_file)
                except Exception as e:
                    print(e) if not self.no_log else 1
                    err_msg = f"{self.add_info}{self._e['json报错']}"
                    error_list.append(err_msg)
            if error_list:
                return error_list
            else:
                return 0
        except Exception as e:
            print(e) if not self.no_log else 1
            return [f"{self.add_info}{self._e['make_result']}", ]

    def write_log(self, log_list: list, log_file: str, add_log=True):
        """
        日志/报错等信息列表记录到文件
        :param log_list: 字符串/字符串列表，待记录对象
        :param log_file: 字符串，记录文件名称,例如："D:\a.txt"
        :param add_log: 附加报错信息，默认为True
        :return:
        """
        print(__name__, self._c, _name()) if not self.no_log else 1
        if isinstance(log_list, str):
            log_list = [log_list, ]
        with codecs.open(log_file, "w", encoding="UTF-8") as log:
            if add_log:
                log.write(f"{self._e['write_log']}")
            for i_log in log_list:
                i_log = f">>> " + i_log + "\n"
                log.write(i_log)

    def write_default_log(self, log_file):
        """生成默认报错文档"""
        print(__name__, self._c, _name()) if not self.no_log else 1
        err_msg = [f"{self._e['write_default_log']}", ]
        self.write_log(log_list=err_msg, log_file=log_file)


@_pre_class
class Model(object):
    """no use"""

    def __init__(self, add_info="", no_log=False, lang=LANG):
        """
        文本
        Text
        :param add_info: 字符串，附加信息
        :param no_log: 不打印调用及报错信息，默认为False
        :param lang: 字符串，选择报错语言，可选["CN", "EN"]，默认CN
        """
        self.add_info = add_info
        self.no_log = no_log
        self.lang = lang
        self._c = self.__class__.__name__  # 类名
        self._e = self.lang_dic[self.lang][self._c]  # 报错字典初定位
        self._cne = self.lang_dic["CN"][self._c]  # 报错中文字典初定位
        self._ene = self.lang_dic["EN"][self._c]  # 报错英文字典初定位

    def __repr__(self):
        return 'Model(add：{0.add_info!r}, quiet：{0.no_log!r}, lang：{0.lang!r})'.format(self)

    def __str__(self):
        return '(add：{0.add_info!s},  quiet：{0.no_log!s}, lang：{0.lang!s})'.format(self)

    def hello_world(self):
        """"""
        print(__name__, self._c, _name()) if not self.no_log else 1
        print(f"{self._e['hello_world']}")
        # print(f"{self._cne['hello_world']}")
        # print(f"{self._ene['hello_world']}")


if __name__ == "__main__":
    sys.stderr.write("Hey, bro, this is a check module [v2].  ")
    sys.exit(1)
