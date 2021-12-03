#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
General check module +
Check object: str num list file +
@reference: Lihuan
@author: WangMing
Maintenance records:
2021.10.20
* 修复 列表类型检查时，重复去除首个元素问题
* 修复 列表数值范围检查时，索引错误问题
* 调整 行/列固定内容检查时，报错语逻辑，增加原固定内容输出展示
2021.10.21
* 调整 check file 类型（文件检查报错返回为列表形式）函数增加文件存在性检查
* 调整 (pre_)check_file_content函数，允许源文件修改（删空行、空格）
* 调整 make_dir函数不删除已存在目录重建的选项
* 新增 复制文件函数（copy_file）,函数特色：目标文件路径不存在将以此创建
2021.10.25
* 新增 check_file_content函数 ck_row_list及ck_col_list参数 0/None/-1 的选项，类似ck_col_type_list
* 新增 check_file_content函数 对行列数范围的检查
2021.10.27
* 修复 check_file_base 检查二进制文件如xlsx编码时错误退出情况，推荐使用file_xlsx2txt函数转换后使用该函数
* 修复 file_xlsx2txt 新增na_values参数作为输入文件缺失值，防止额外处理缺失值的情况
2021.10.28
* 修复 check_file_base 检查文件为ANSI编码且包含各种特殊字符时，编码识别不准确的问题
* 修复 check_file_content函数 列表长度范围检查参数传递不准确问题
* 修复 list_num_ban函数 禁用值为单个数值时报错问题
* 修复 check_file_content函数 检查数值禁用值及数值范围检查时错误传参问题
2021.11.2
* 修复 _get_encoding函数 所有编码都是兼容ASCII，解决显示iso-8859-1与索引打印ASCII不符的问题，统一ASCII码以GBK格式读入
* 优化 list_dup函数，当list和转化set后长度一致时，直接返回0，提高检查速度
* 优化 check_file_content函数 新增pre_check参数，使pre_check_file_content函数调用可控，避免外部调用后二次检查
2021.11.3
* 修复 check_com_line函数 报错语提示行列数提示不准确bug
** 修复 com_list函数 报错检查错误返回bug
2021.11.10
* 修复 check_file_base函数 文件编码格式符合要求时意外报错的bug
2021.11.12
* 新增 _get_encoding2函数，提供linux.file命令获取文件编码的方式
** 修复 file_encoding、check_file_base函数，当utf8文件存在少量中文偶发性出现编码识别错误的问题，提供use_1参数，切换编码识别方法
* 修复 num_range函数 报错语上下限相反的错误
* 修复 check_str、str_chinese函数 检查中文字符报错语错误
2021.11.15
* 修复 部分函数列表中存在数值及部分数值未转化字符串引起的报错问题
* 修复 list_num_range、check_file_content函数报错语上下限相反的问题
2021.11.30
* 修复 file_xlsx2txt、pre_check_file_content处理文件含有"异常的问题
* 修复 pre_check_file_content额外处理缺失数据的问题
* 新增 所有函数调用及报错时是否打印信息的控制，由参数no_log控制，默认打印
** 修改 file_encoding、check_file_base函数，默认使用use_1=False
"""
# ---- ---- ---- ---- ---- #
import sys
import os
import re
import codecs
import chardet
import subprocess
import shutil
import pandas as pd
from collections import Counter
from zipfile import ZipFile
from functools import wraps


# import json
# import glob
# import argparse


def call_log(func):
    """函数调用记录"""

    @wraps(func)
    def with_logging(*args, **kwargs):
        if "no_log" not in kwargs or not kwargs["no_log"]:
            print("调用 " + func.__name__)
        return func(*args, **kwargs)

    return with_logging


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


def _convert_size(size_str):
    """
    将M/K结尾的文件大小转换为对应字节数，不合规默认为0字节
    :param size_str:
    :return: 正常返回转换为字节后的文件大小
    """
    convert_size = 0
    spat = re.compile(r"([0-9]+)([A-Za-z]*)")
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
    推测文件编码格式，备选（linux file）
    :param in_file: 字符串，文件名
    :return: 正常返回推测的文件编码格式（大写）
    """
    code_format = os.popen(f"file --mime-encoding {in_file}").read().rstrip('\n').split(':')[1].upper()
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


@call_log
def str_length(in_str: str, length: int = None, min_len: int = 1, max_len: int = 20, other_str="", add_info="",
               no_log=False):
    """
    判断字符串长度是否在范围内（max_len应大于等于min_len）
    :param in_str: 字符串，检查对象
    :param length: 整数，字符串长度固定值，优先级高于范围检查，None表示不检查固定值
    :param min_len: 整数，字符串长度下限，默认1
    :param max_len: 整数，字符串长度上限，默认20
    :param other_str: 字符串，报错信息中替换输入字符串为其他内容，""表示不替换，显示输入字符串
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 范围内返回0，范围外返回字符串报错信息
    """
    try:
        s_str = other_str if other_str else in_str
        if length is not None:
            if len(in_str) == length:
                return 0
            else:
                return f"{add_info}{s_str}长度为{len(in_str)}，要求长度为：{length}"
        elif len(in_str) >= min_len:
            if len(in_str) <= max_len:
                return 0
            else:
                return f"{add_info}{s_str}长度为{len(in_str)}，超过上限：{max_len}"
        else:
            return f"{add_info}{s_str}长度为{len(in_str)}，低于下限：{min_len}"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}字符串长度检查时出错"


@call_log
def str_format(in_str: str, re_obj=None, re_ban_body=None, ck_head=True, re_ban_head=None,
               ck_tail=False, re_ban_tail=None, other_str="", add_info='', no_log=False):
    """
    字符串正则范围内检查（默认以字母/非零数字开头，仅包含字母、数字、点和中划线）
    :param in_str: 字符串，检查对象
    :param re_obj: re.compile对象，允许的正则格式编译，默认re.compile(r"^[A-Za-z1-9][A-Za-z0-9-.]*$")
    :param re_ban_body: re.compile对象，错误的主体字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9-.]")
    :param ck_head: 布尔值，是否检查字符串首个字符，默认True
    :param re_ban_head: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"^[^A-Za-z1-9]")
    :param ck_tail: 布尔值，是否检查字符串末尾字符，默认False
    :param re_ban_tail: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9]$")
    :param other_str: 字符串，报错信息中替换输入字符串为其他内容，""表示不替换，显示输入字符串
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 范围内返回0，范围外返回字符串报错信息
    """
    try:
        s_str = other_str if other_str else in_str
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
        if re.match(re_obj, in_str):
            return 0
        else:
            msg1 = ""
            msg2 = ""
            msg3 = ""
            ill_list = re.findall(re_ban_body, in_str)
            if ill_list:
                msg1 = f"{add_info}在{s_str}中发现非法字符：{_join_str(ill_list)}；"
            ill_start = re.findall(re_ban_head, in_str)
            if ill_start:
                msg2 = f"{add_info}在{s_str}中发现非法起始字符：{_join_str(ill_start)}"
            if ck_tail:
                ill_end = re.findall(re_ban_tail, in_str)
                if ill_end:
                    msg3 = f"{add_info}在{s_str}中发现非法结尾字符：{_join_str(ill_start)}"
            msg = msg1 + msg2 + msg3
            if not msg:
                msg = f"{add_info}{s_str}中发现非法字符，但无法获取错误类型"
            return msg
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}字符串正则检查时出错"


@call_log
def str_chinese(in_str, other_str="", add_info='', no_log=False):
    """
    字符串中是否有中文检查
    :param in_str: 字符串，检查对象
    :param other_str: 字符串，报错信息中替换输入字符串为其他内容，""表示不替换，显示输入字符串
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 无中文返回0，有中文返回字符串报错信息
    """
    try:
        s_str = other_str if other_str else in_str
        in_str = str(in_str)
        str_list = []
        for i_str in in_str:
            if "\u4e00" <= i_str <= "\u9fa5":
                str_list.append(i_str)
        if len(str_list) != 0:
            return f'{add_info}{s_str}中发现中文字符：{_join_str(str_list)}'
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}中文字符串检查时出错"


@call_log
def str_ban(in_str, ban_list=None, other_str="", add_info="", no_log=False):
    """
    便捷字符串禁用字符检查（完整版使用str_format）
    :param in_str: 字符串，检查对象
    :param ban_list: 迭代器，所有不支持的字符，None表示无禁用
    :param other_str: 字符串，报错信息中替换输入字符串为其他内容，""表示不替换，显示输入字符串
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return:无禁用返回0，有禁用返回字符串报错信息
    """
    try:
        s_str = other_str if other_str else in_str
        if ban_list is None:
            ban_list = []
        error_list = []
        for i in ban_list:
            if str(i) in in_str:
                error_list.append(i)
        if not error_list:
            return 0
        else:
            return f'{add_info}{s_str}中发现非法字符：{_join_str(error_list)}'
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}字符串禁用检查时出错"


@call_log
def check_str(in_str: str, ck_length=True, ck_format=True,
              ck_chinese=True, ck_ban=True, allow_space=False,
              length: int = None, min_len: int = 1, max_len: int = 20,
              re_obj=None, re_ban_body=None, ck_head=True, re_ban_head=None,
              ban_list: list = None,
              other_str="", add_info: str = "", no_log=False):
    """
    字符串检查
    :param in_str: 字符串，检查对象
    :param ck_length: 布尔值，是否检查长度，默认True
    :param ck_format: 布尔值，是否检查正则格式，默认True（以字母/非零数字开头，仅包含字母、数字、点和中划线）
    :param ck_chinese: 布尔值，是否检查中文字符，默认True
    :param ck_ban: 布尔值，是否检查禁用字符，默认True
    :param allow_space: 布尔值，是否允许空格，默认False
    :param length: 整数，字符串长度固定值，优先级高于范围检查，None表示不检查固定值
    :param min_len: 整数，字符串长度下限，默认1
    :param max_len: 整数，字符串长度上限，默认20
    :param re_obj: re.compile对象，允许的正则格式编译，默认re.compile(r"^[A-Za-z1-9][A-Za-z0-9-.]*$")
    :param re_ban_body: re.compile对象，错误的主体字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9-.]")
    :param ck_head: 布尔值，是否检查字符串首个字符
    :param re_ban_head: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"^[^A-Za-z1-9]")
    :param ban_list: 迭代器，所有不支持的字符，None表示不检查禁用字符，忽视ck_ban
    :param other_str: 字符串，报错信息中替换输入字符串为其他内容，""表示不替换，显示输入字符串
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    try:
        error_list = []
        s_str = other_str if other_str else in_str
        if not ck_chinese:  # 如果不禁用中文字符，那么将所有中文字符替换为"a",规避正则检查
            in_str = re.sub('[\u4e00-\u9fa5]', 'a', in_str)
        if allow_space:  # 如果允许空格，那么将所有空格替换为"b",规避正则检查
            in_str = re.sub(' ', 'b', in_str)
        if ck_length:
            err_msg = str_length(in_str=in_str, length=length, max_len=max_len, min_len=min_len,
                                 other_str=s_str, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if ck_format:
            err_msg = str_format(in_str=in_str, re_obj=re_obj, re_ban_body=re_ban_body,
                                 ck_head=ck_head, re_ban_head=re_ban_head, other_str=s_str, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if ck_chinese:
            err_msg = str_chinese(in_str=in_str, other_str=s_str, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if ck_ban and ban_list is not None:
            err_msg = str_ban(in_str=in_str, ban_list=ban_list, other_str=s_str, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if len(error_list) == 0:
            return 0
        else:
            return error_list
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}字符串检查时出错", ]


@call_log
def num_range(num: float, min_num=float('-inf'), max_num=float('inf'), add_info="", no_log=False):
    """
    数值范围内检查
    :param num: 浮点数，检查对象
    :param min_num: 浮点数，取值下限
    :param max_num: 浮点数，取值上限
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 范围内返回0，范围外返回字符串报错信息
    """
    try:
        if min_num <= num <= max_num:
            return 0
        else:
            min_num = '负无穷' if min_num == float('-inf') else min_num
            max_num = '正无穷' if max_num == float('inf') else max_num
            return f"{add_info}下限为{min_num}，上限为{max_num}，给定数值{num}超出了界限"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}数值范围检查时出错"


@call_log
def num_ban(num: float, ban_num: list = None, add_info="", no_log=False):
    """
    数值禁用值检查
    :param num: 浮点数,检查对象
    :param ban_num: 数值/数值列表，所有不支持的数值，None表示无禁用
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 无禁用返回0，有禁用返回字符串报错信息
    """
    try:
        if not isinstance(ban_num, list):
            ban_num = [ban_num, ]
        if ban_num is None:
            ban_num = []
        error_list = []
        for i in ban_num:
            if i == float(num):
                error_list.append(i)
        if not error_list:
            return 0
        else:
            return f"{add_info}发现禁用数值：{_join_str(error_list)}"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}数值禁用检查时出错"


@call_log
def check_num(num: float, ck_range=True, ck_ban=True,
              min_num=float('-inf'), max_num=float('inf'),
              ban_num: list = None,
              add_info="", no_log=False):
    """
    数值检查
    :param num: 浮点数，检查对象
    :param ck_range: 布尔值，是否检查大小范围，默认True
    :param ck_ban: 布尔值，是否检查禁用值，默认True
    :param min_num: 浮点数，取值下限，默认负无穷
    :param max_num: 浮点数，取值上限，默认正无穷
    :param ban_num: 数值/数值列表，所有不支持的数值，None表示不检查禁用值，忽视ck_ban
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    try:
        error_list = []
        if ck_range is True:
            err_msg = num_range(num=num, min_num=min_num, max_num=max_num, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg} ")
        if ck_ban and ban_num is not None:
            err_msg = num_ban(num=num, ban_num=ban_num, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg} ")
        if len(error_list) == 0:
            return 0
        else:
            return error_list
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}数值检查时出错", ]


@call_log
def file_exist(in_file, add_info="", no_log=False):
    """
    文件存在检查
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 存在返回0，不存在返回字符串报错信息
    """
    try:
        if os.path.exists(in_file):
            return 0
        else:
            in_file_name = os.path.basename(in_file)
            return f"{add_info}输入文件文件{in_file_name}不存在，请检查"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}文件存在检查时出错"


@call_log
def file_suffix(in_file, suffix_list: list = None, add_info="", no_log=False):
    """
    文件后缀名检查（检查in_file是否以suffix_list中某一个元素结尾，不区分大小写）
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param suffix_list: 字符串/字符串列表，允许使用的格式名，不区分大小写，默认txt
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 匹配到返回0，否则返回字符串报错信息
    """
    try:
        if suffix_list is None:
            suffix_list = ['txt', ]
        if isinstance(suffix_list, str):
            suffix_list = [suffix_list.lower(), ]
        else:
            suffix_list = list(map(lambda x: x.lower(), suffix_list))
        for i_suf in suffix_list:
            re_obj = re.compile(str(i_suf) + r"$")
            if re.search(re_obj, in_file):
                return 0
        in_file_name = os.path.basename(in_file)
        return f"{add_info}{in_file_name}后缀不被支持，只允许使用{_join_str(suffix_list)}作为后缀的文件"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}文件后缀检查时出错"


@call_log
def file_null(in_file, add_info="", no_log=False):
    """
    判断是否为空文件
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 非空返回0，空返回字符串报错信息
    """
    try:
        if os.path.getsize(in_file) == 0:
            in_file_name = os.path.basename(in_file)
            return f"{add_info}输入文件{in_file_name}的大小为0，请检查文件是否为空"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}空文件检查时出错"


@call_log
def file_size(in_file, max_size="50M", add_info="", no_log=False):
    """
    检查文件大小是否超出限制
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param max_size: 字符串，以K/M结尾，文件大小上限，默认"50M"
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 未超出返回0，超出返回字符串报错信息
    """
    try:
        max_byte = _convert_size(max_size)
        doc_size = os.path.getsize(in_file)
        if doc_size > max_byte:
            in_file_name = os.path.basename(in_file)
            return f"{add_info}输入文件{in_file_name}的大小为{doc_size},超过了{max_size}的限制"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}文件大小检查时出错"


@call_log
def file_encoding(in_file, allowed_encode: list = None, use_1=False, add_info="", no_log=False):
    """
    检查编码格式是否在允许范围内（默认UTF-8）（二进制文件如xlsx，无法检测文件编码）
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param allowed_encode: 字符串/字符串列表，允许的编码格式，不区分大小写,默认UTF-8
    :param use_1: 布尔值，默认False，True表示使用python.chardet模块推测文件编码，False表示使用linux.file命令获取文件编码
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 范围内返回0，范围外返回字符串，推测的文件编码格式（大写），二进制文件返回None
    """
    try:
        if allowed_encode is None:
            allowed_encode = ["UTF-8", ]  # ["UTF-8", "GBK", "GB2312"]
        if isinstance(allowed_encode, str):
            allowed_encode = [allowed_encode.upper(), ]
        else:
            allowed_encode = list(map(lambda x: x.upper(), allowed_encode))
        if use_1:
            doc_encoding = _get_encoding(in_file)
        else:
            doc_encoding = _get_encoding2(in_file)
        if doc_encoding in allowed_encode:
            return 0
        else:
            return doc_encoding
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}文件编码检查时出错"


@call_log
def file_convert(in_file, in_code: str = "UTF-8", out_file=None, out_code="UTF-8", add_info="", no_log=False):
    """
    文件编码转换
    :param in_file: 字符串，输入对象，例如："D:\a.txt"
    :param in_code: 字符串，输入文件编码，不区分大小写，默认"UTF-8"，云平台前端限制：txt文件仅UTF-8及UTF-8-BOM可上传
    :param out_file: 字符串，输出对象，例如："D:\b.txt"，默认在in_file后添加".convert"
    :param out_code: 字符串，输出文件编码，目标格式，不区分大小写，默认"UTF-8"
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回0，失败返回字符串报错信息
    """
    try:
        if out_file is None:
            out_file = str(in_file) + '.convert'
        flag = ''
        if os.path.abspath(in_file) == os.path.abspath(out_file):
            flag += '1'
            out_file = str(out_file) + '.convert'
        in_file_name = os.path.basename(in_file)
        # if not in_code:
        #     return f"{add_info}{in_file_name}编码格式不被支持，请转为{out_code}编码后重试"
        in_code = in_code.upper()
        out_code = out_code.upper()
        try:
            with codecs.open(out_file, "w", out_code) as fileOU:
                for i in _read_file(in_file, in_code=in_code):
                    if isinstance(i, Exception):
                        return repr(i)
                    fileOU.write(i)
            if flag:
                os.system(f'cp -r {out_file} {in_file}')
                os.system(f'rm {out_file}')
            return 0
        except Exception as e:
            print(e)
            return f"{add_info}将文件{in_file_name}从{in_code}转为{out_code}时发生错误，请尝试自己转换编码后重投任务"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}文件编码转换时出错"


file_convert_encoding = file_convert


@call_log
def file_xlsx2txt(in_file, out_file: str = None, sheet_no=1, sep="\t", na_values: list = None, na_rep="", add_info="",
                  no_log=False):
    """
    文件格式转换（xlsx to txt）
    :param in_file: 字符串，输入对象，例如："D:\a.xlsx"
    :param out_file: 字符串，输入对象，例如："D:\a.txt"，None表示输出为同名但后缀为txt的文件
    :param sheet_no: 正整数，转换的sheet表号，默认1
    :param sep: 字符串，分隔符，默认"\t"
    :param na_values: 字符串列表，in_file中表示缺失值的字符串，默认None，表示维持原样，无默认缺失
    :param na_rep: 字符串，out_file中表示缺失值的字符串，默认""
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 转换成功返回0，转换失败返回字符串报错信息
    """
    in_file_name = os.path.basename(in_file)
    try:
        if out_file is None:
            out_file = os.path.splitext(in_file)[0] + '.txt'
        df = pd.read_excel(in_file, sheet_name=sheet_no - 1, keep_default_na=False, na_values=na_values)
        df.to_csv(out_file, sep=sep, na_rep=na_rep, index=False, quotechar=sep)
    except Exception as e:
        print(e) if not no_log else 1
        return f'{add_info}文件{in_file_name}格式转换时出错'
    else:
        return 0


@call_log
def check_file_base(in_file, ck_exist=True, ck_suffix=True, ck_null=True,
                    ck_size=True, ck_encoding=True, use_1=False, do_convert=True,
                    suffix_list: list = None,
                    max_size="50M",
                    allowed_encode: list = None,
                    out_file=None, out_code="UTF-8",
                    add_info="", no_log=False):
    """
    文件基础检查（存在，后缀，空文件，大小，编码）,提供转码选项(仅use_1=True消除BOM)，仅当提供一种allowed_encode时有效
    注意：文件编码检查及转码仅对非二进制文件有效，xlsx文件推荐使用file_xlsx2txt函数转换后进行文件检查
    注意：如果out_file与in_file同路径且同名，将覆盖原文档
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
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
    :param out_file: 字符串，输出对象,例如："D:\b.txt"，默认在in_file后添加".convert"
    :param out_code: 字符串，输出文件编码，默认UTF-8
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    if allowed_encode is None:
        allowed_encode = ["UTF-8", ]
    if isinstance(allowed_encode, str):
        allowed_encode = [allowed_encode.upper(), ]
    try:
        error_list = []
        if ck_exist:
            err_msg = file_exist(in_file=in_file, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if ck_suffix:
            err_msg = file_suffix(in_file=in_file, suffix_list=suffix_list, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if ck_null:
            err_msg = file_null(in_file=in_file, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if ck_size:
            err_msg = file_size(in_file=in_file, max_size=max_size, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}{err_msg}")
        if ck_encoding:
            err_msg = file_encoding(in_file=in_file, allowed_encode=allowed_encode, use_1=use_1, no_log=no_log)
            if err_msg is None:
                error_list.append(f"{add_info}推测{os.path.basename(in_file)}文件为二进制文件（如xlsx），无法识别文件编码及转码")
            elif do_convert and len(allowed_encode) == 1:
                if err_msg:
                    in_code = err_msg  # 当UTF-8文件存在少量中文或特殊符号时，使用use_1=True可能存在识别不准确的问题
                    # in_code = "UTF-8"  # 云平台前端限制txt文件编码仅可为UTF-8或UTF-8-BOM，这里可默认UTF-8
                else:
                    in_code = allowed_encode[0]
                err_msg = file_convert(in_file=in_file, out_file=out_file,
                                       in_code=in_code, out_code=out_code, no_log=no_log)
                if err_msg:
                    error_list.append(f"{add_info}{err_msg}")
            elif err_msg and not do_convert:
                error_list.append(f"{add_info}推测文件编码格式为{err_msg}或ASCII，不符合要求，转换为{allowed_encode}后重试")
        if len(error_list) == 0:
            return 0
        else:
            return error_list
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}文件基础检查时出错", ]


@call_log
def get_row_num(in_file, no_log=False):
    """
    获取文件行数
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回整数
    """
    try:
        out = subprocess.getoutput("awk 'END{print NR}' %s" % in_file)
        return int(out.split()[0])
    except Exception as e:
        print(e) if not no_log else 1


@call_log
def get_col_num(in_file, sep='\t', no_log=False):
    """
    获取文件列数（列数不一致时，以最后一行统计为准）
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param sep: 字符串，分隔符，默认"\t"
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回整数
    """
    try:
        out = subprocess.getoutput("awk -F '%s' 'END{print NF}' %s" % (sep, in_file))
        return int(out)
    except Exception as e:
        print(e) if not no_log else 1


@call_log
def get_row_line(in_file, line_num=1, no_log=False):
    """
    获取文件指定一行（整行作为字符串读入），默认读第一行
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param line_num: 正整数，指定读取行号，默认1
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回指定行字符串，错误无返回
    """
    try:
        for line, line_no in _read_line(in_file, rm_br=True):
            if line_no < line_num:
                continue
            elif line_no > line_num:
                return None
            else:
                return line
    except Exception as e:
        print(e) if not no_log else 1


get_row = get_line = get_row_line


@call_log
def file_line_dup(in_file, add_info='', no_log=False):
    """
    数据重复行检查
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 无重复返回0，有重复返回字符串报错信息
    """
    try:
        res_list = []
        err = []
        for line, line_no in _read_line(in_file):
            if line in res_list:
                err.append(line_no)
            else:
                res_list.append(line)
        if err:
            in_file_name = os.path.basename(in_file)
            return f'{add_info}{in_file_name}发现重复行，行号：{_join_str(err)}'
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1


@call_log
def line_blank(in_line, add_info='', no_log=False):
    """
    空白行检查（除空白字符外，无其他内容）
    :param in_line: 字符串，检查对象,例如："D:\a.txt"
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 非空白行返回0，空白行返回字符串报错信息
    """
    try:
        in_line = in_line.strip()
        blank_pat = re.compile(r"^\s*$")
        if re.search(blank_pat, in_line):
            return f"{add_info}发现空白行, 请检查"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查空行时出错"


@call_log
def line_sep(in_line, sep_r=r'\t', add_info='', no_log=False):
    """
    分隔符规范检查（开头分隔符、连用分隔符、分隔符前后空白、结尾空白）
    :param in_line: 字符串，检查对象,例如："D:\a.txt"
    :param sep_r: 字符串，纯文本读入的分隔符，含有与正则有关的字符应在字符串前加r,或将字符使用'\'转义,默认r'\t'
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 规范返回0，不规范返回字符串报错信息
    """
    try:
        head_sep = re.compile(f"^[{sep_r}]")
        sep_sep = re.compile(f"{sep_r}{sep_r}")
        blank_sep = re.compile(rf"\s{sep_r}")
        sep_blank = re.compile(rf"{sep_r}\s")
        tail_blank = re.compile(r"\s$")
        msg = ''
        if re.search(head_sep, in_line):
            msg = msg + f"发现了以{sep_r}分隔符开头；"
        if re.search(sep_sep, in_line):
            msg = msg + f"发现了连续的{sep_r}分隔符；"
        if re.search(blank_sep, in_line):
            msg = msg + f"{sep_r}分隔符前发现了可疑空白；"
        if re.search(sep_blank, in_line):
            msg = msg + f"{sep_r}分隔符后发现了可疑空白；"
        if re.search(tail_blank, in_line):
            msg = msg + f"发现了空白结尾字符；"
        if msg == "":
            return 0
        else:
            return f'{add_info}{msg}请检查'
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查分隔符规范时出错"


@call_log
def get_row2list(in_file, row_no=1, sep="\t",
                 rm_blank=True, fill_null=False, null_list: list = None, no_log=False):
    """
    获取文件指定一行的元素列表，并默认移除元素前后空白，默认第一行
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param row_no: 正整数，指定读取行号，默认1
    :param sep: 字符串，指定行元素间分隔符，默认"\t"
    :param rm_blank: 布尔值，是否移除该行元素前后空白，默认True
    :param fill_null: 布尔值，是否将缺失数据统一替换为NA，默认False
    :param null_list: 字符串/字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回指定行元素列表，错误无返回
    """
    try:
        if isinstance(null_list, str):
            null_list = [null_list, ]
        if null_list is None:
            null_list = ["", "NA", "N/A", "NULL"]
        line_list = []
        for line, line_no in _read_line(in_file):
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
    except Exception as e:
        print(e) if not no_log else 1


@call_log
def get_col2list(in_file, col_no=1, sep="\t",
                 rm_blank=True, fill_null=True, null_list: list = None, no_log=False):
    """
    获取文件指定一列的元素列表，并默认移除元素前后空白，默认第一列
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param col_no: 正整数，指定读取行号，默认1
    :param sep: 字符串，指定行元素间分隔符，默认"\t"
    :param rm_blank: 布尔值，是否移除该列元素前后空白，默认True
    :param fill_null: 布尔值，是否将缺失数据统一替换为NA，默认True
    :param null_list: 字符串/字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回指定列元素列表，错误无返回
    """
    try:
        if isinstance(null_list, str):
            null_list = [null_list, ]
        if null_list is None:
            null_list = ["", "NA", "N/A", "NULL"]
        col_elements = []
        for row, no in _read_line(in_file):
            row_list = row.split(sep)
            if rm_blank:
                row_list = list(map(lambda x: x.strip(), row_list))
            if fill_null:
                row_list = ["NA" if x in null_list else x for x in row_list]
            col_element = row_list[col_no - 1]
            col_elements.append(col_element)
        return col_elements
    except Exception as e:
        print(e) if not no_log else 1


@call_log
def list_length(in_list, exp_len: int = None, min_len=0, max_len: int = float('inf'), key="元素", add_info="",
                no_log=False):
    """
    检查列表长度是否为固定长度/在范围内，固定长度检查优先级高于范围内检查
    :param in_list: 列表，检查对象
    :param exp_len: 整数，期望固定长度，优先级高于范围内检查，None表示执行范围内检查
    :param min_len: 整数，最小长度，length=None时使用，默认0
    :param max_len: 整数，最大长度，length=None时使用，默认正无穷
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 为固定长度/在范围内返回0，否则返回字符串报错信息
    """
    try:
        if isinstance(in_list, str):
            list_len = 1
        else:
            list_len = len(list(in_list))
        if exp_len is None:
            if max_len >= list_len >= min_len:
                return 0
            else:
                max_len = "无穷" if max_len == float('inf') else max_len
                return f"{add_info}有{list_len}个{key}，{key}个数应在[{min_len},{max_len}]范围内"
        else:
            if list_len != exp_len:
                return f"{add_info}有{list_len}个{key}，应为{exp_len}个{key}"
            else:
                return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查长度时出错"


@call_log
def list_range(in_list, min_len=0, max_len: int = float('inf'), key='元素', add_info="", no_log=False):
    """
    检查列表长度是否在范围内
    :param in_list: 列表，检查对象
    :param min_len: 整数，最小长度，默认0
    :param max_len: 整数，最大长度，默认正无穷
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 范围内返回0，范围外返回字符串报错信息
    """
    return list_length(in_list=in_list, min_len=min_len, max_len=max_len, key=key, add_info=add_info, no_log=no_log)


@call_log
def list_dup(in_list, key='元素', add_info="", no_log=False):
    """
    检查列表中的重复元素
    :param in_list: 列表，检查对象
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 无重复0，有重复返回字符串报错信息
    """
    try:
        in_list = list(map(lambda x: str(x), in_list))
        in_list = list(map(lambda x: x.strip(), in_list))
        if len(in_list) == len(set(in_list)):
            return 0
        list_count = dict(Counter(in_list))
        dup_item = [key for key, value in list_count.items() if value > 1]
        if not dup_item:
            return 0
        else:
            return f"{add_info}存在重复的{key}{_join_str(dup_item)}，请检查"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查重复时出错"


@call_log
def list_ban(in_list, ban_list: list = None, key='元素', add_info="", no_log=False):
    """
    检查列表中的禁用元素
    :param in_list: 列表，检查对象
    :param ban_list: 字符串/字符串列表，禁用元素，默认[]，即无禁用
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 无禁用返回0，有禁用返回字符串报错信息
    """
    try:
        if isinstance(ban_list, str):
            ban_list = [ban_list, ]
        if ban_list is None:
            ban_list = []
        in_list = list(map(lambda x: str(x), in_list))
        ban_list = list(map(lambda x: str(x), ban_list))
        ban_item = set(in_list).intersection(set(ban_list))
        if ban_item:
            return f"{add_info}{key}{_join_str(ban_item)}，请检查"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查禁用时出错"


@call_log
def list_na(in_list, na_list: list = None, key='元素', add_info="", no_log=False):
    """
    检查列表中是否包含缺失数据
    :param in_list: 列表，检查对象
    :param na_list: 字符串/字符串列表，定义为缺失数据的字符类型列表，默认("", "NA", "N/A", "NULL")
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 无缺失返回0，有缺失返回字符串报错信息
    """
    try:
        if isinstance(na_list, str):
            na_list = [na_list, ]
        if na_list is None:
            na_list = ["", "NA", "N/A", "NULL"]
        add_info = add_info + '含有空或缺失'
        return list_ban(in_list=in_list, ban_list=na_list, key=key, add_info=add_info, no_log=no_log)
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查缺失时出错"


@call_log
def list_format(in_list, re_obj=None, re_ban_body=None, ck_head=True, re_ban_head=None,
                ck_tail=False, re_ban_tail=None, rm_first=False, key='元素', add_info='', no_log=False):
    """
    列表字符串正则范围内检查（默认以字母/数字开头，仅包含字母、数字、点和中划线和下划线）
    :param in_list: 列表，检查对象
    :param re_obj: re.compile对象，允许的正则格式编译，默认re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._-])*$')
    :param re_ban_body: re.compile对象，错误的主体字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9._-]")
    :param ck_head: 布尔值，是否检查字符串首个字符，默认True
    :param re_ban_head: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"^[^A-Za-z0-9]")
    :param ck_tail: 布尔值，是否检查字符串末尾字符，默认False
    :param re_ban_tail: re.compile对象，错误的开头字符的正则格式编译，默认re.compile(r"[^A-Za-z0-9]$")
    :param rm_first: 布尔值，默认False,是否去掉首个元素，当文件有标题行时选True
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 范围内返回0，范围外返回字符串报错信息
    """
    try:
        if rm_first:
            in_list = in_list[1:]
        if re_obj is None:
            re_obj = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._-])*$')
            if re_ban_body is None:
                re_ban_body = re.compile(r"[^A-Za-z0-9._-]")
            if ck_head and re_ban_head is None:
                re_ban_head = re.compile(r"^[^A-Za-z0-9]")
            if ck_tail and re_ban_tail is None:
                re_ban_tail = re.compile(r"[^A-Za-z0-9]$")
        error_item = []
        for i in in_list:
            err_msg = str_format(in_str=i, re_obj=re_obj, re_ban_body=re_ban_body,
                                 ck_head=ck_head, re_ban_head=re_ban_head, re_ban_tail=re_ban_tail, no_log=True)
            if err_msg:
                error_item.append(i)
        if error_item:
            return f"{add_info}检查到不合规{key}{_join_str(error_item)}"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查字符串使用规范时出错"


@call_log
def list_factor(in_list, exp_num=None, min_num=1, max_num: int = float('inf'),
                rm_first=False, key='元素', add_info="", no_log=False):
    """
    列表因子（非重复元素）个数检查
    :param in_list: 列表，检查对象
    :param exp_num: 整数，期望因子个数，优先级高于范围内检查，None表示执行范围内检查
    :param min_num: 整数，最小个数，exp_num=None时使用，默认1
    :param max_num: 整数，最小个数，exp_num=None时使用，默认正无穷
    :param rm_first: 布尔值，默认False,是否去掉首个元素，当文件有标题行时选True
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 范围内返回0，范围外返回字符串报错信息
    """
    try:
        if rm_first:
            in_list = in_list[1:]
        in_list = list(set(in_list))
        msg = list_length(in_list, exp_len=exp_num, min_len=min_num, max_len=max_num, key=key, no_log=no_log)
        if msg:
            return f"{add_info}{msg}"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查类别数时出错"


list_factor_num = list_class_num = list_group_num = list_factor


@call_log
def list_type(in_list, exp_type='float', rm_first=False, add_info="", no_log=False):
    """
    检查列表元素类型，并转换期望元素类型的新列表
    :param in_list: 列表，检查对象
    :param exp_type: 字符串，期望列表元素类型，限定为python支持的格式,如[int,float,str,bool,...]，默认"float"
    :param rm_first: 布尔值，默认False,是否去掉首个元素，当文件有标题行时选True
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回新列表，异常返回字符串报错信息
    """
    try:
        if rm_first:
            in_list = in_list[1:]
        # flag = [isinstance(x, eval(exp_type)) for x in in_list]
        # print(flag)
        new_list = list(map(eval(exp_type.lower()), in_list))
        return new_list
    except ValueError as e:
        return f"{add_info}检查到非{exp_type}类值：" + str(e).split(':')[-1]
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查类型时出错"


@call_log
def list_num_range(in_list, min_num=float('-inf'), max_num=float('inf'), rm_first=False, key='数值', add_info="",
                   no_log=False):
    """
    检查数值列表元素数值是否在范围内
    :param in_list: 列表，检查对象
    :param min_num: 浮点数，数值下限，默认负无穷
    :param max_num: 浮点数，数值上限，默认正无穷
    :param rm_first: 布尔值，默认False,是否去掉首个元素，当文件有标题行时选True
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回0，异常返回字符串报错信息
    """
    try:
        if rm_first:
            in_list = in_list[1:]
        err_list = []
        for i in range(1, len(in_list) + 1):
            msg = num_range(num=in_list[i - 1], min_num=min_num, max_num=max_num, add_info=f'第{i}个数值：', no_log=True)
            if msg:
                err_list.append(i)
        if err_list:
            min_num = '负无穷' if min_num == float('-inf') else min_num
            max_num = '正无穷' if max_num == float('inf') else max_num
            return f"{add_info}第{_join_str(err_list)}个{key}超出界限，下限为{min_num}，上限为{max_num}"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查数值范围时出错"


@call_log
def list_num_ban(in_list, ban_num: list = None, rm_first=False, key='数值', add_info="", no_log=False):
    """
    检查数值列表元素数值有无禁用值
    :param in_list: 列表，检查对象
    :param ban_num: 数值/数值列表，禁用数值，None表示无禁用限制
    :param rm_first: 布尔值，默认False,是否去掉首个元素，当文件有标题行时选True
    :param key: 字符串，关键字
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回0，异常返回字符串报错信息
    """
    try:
        if rm_first:
            in_list = in_list[1:]
        err_list = []
        if isinstance(ban_num, float) or isinstance(ban_num, int):
            ban_num = [ban_num, ]
        for i in range(1, len(in_list) + 1):
            msg = num_ban(num=in_list[i - 1], ban_num=ban_num, add_info="", no_log=True)
            if msg:
                err_list.append(i)
        if err_list:
            return f"{add_info}第{_join_str(err_list)}个{key}为禁用值，禁用值为{_join_str(ban_num)}"
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查数值禁用时出错"


@call_log
def file_com_row_col_num(in_file, sep='\t', row_greater: bool = None,
                         contain_equal=True, add_info='', no_log=False):
    """
    数据行列数大小关系检查
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param sep: 字符串，指定行元素间分隔符，默认'\t'
    :param row_greater: 布尔值，是否行数更多，None表示仅返回比较结果信息，不返回报错信息
    :param contain_equal: 布尔值，是否含等号，作为row_greater参数补充，仅在不为None时生效，默认True
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常[有row_greater参数返回0,无row_greater参数返回字符串检查结果]，异常返回字符串报错信息
    """
    try:
        row_number = get_row_num(in_file=in_file, no_log=no_log)
        col_number = get_col_num(in_file=in_file, sep=sep, no_log=no_log)
        if row_greater is None:
            if row_number > col_number:
                return f"{add_info}行数>列数"
            elif row_number > col_number:
                return f"{add_info}行数<列数"
            else:
                return f"{add_info}行数=列数"
        elif row_greater:
            if contain_equal:
                if row_number < col_number:
                    return f"{add_info}行数<列数，要求行数>=列数"
                else:
                    return 0
            elif row_number <= col_number:
                return f"{add_info}行数<=列数，要求行数>列数"
            else:
                return 0

        else:
            if contain_equal:
                if row_number < col_number:
                    return f"{add_info}行数>列数，要求行数<=列数"
                else:
                    return 0
            elif row_number <= col_number:
                return f"{add_info}行数>=列数，要求行数<列数"
            else:
                return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}检查文件行列数大小关系时出错"


@call_log
def check_file_dim_fix(in_file, sep='\t', row_num_exp: int = None,
                       col_num_exp: int = None, add_info='', no_log=False):
    """
    数据固定维度快捷检查，完整版使用 check_file_content
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param sep: 字符串，分隔符，默认'\t'
    :param row_num_exp: 正整数，期望行数，None表示不检查行数
    :param col_num_exp: 正整数，期望列数，None表示不检查列数
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    try:
        if not os.path.isfile(in_file):
            return [f"{add_info}快捷检查文件固定维度时出错，文件{in_file}不存在或非文件", ]
        error_list = []
        row_number = get_row_num(in_file=in_file, no_log=no_log)
        col_number = get_col_num(in_file=in_file, sep=sep, no_log=no_log)
        in_file_name = os.path.basename(in_file)
        if row_num_exp is not None:
            if row_number != row_num_exp:
                error_list.append(f'{add_info}{in_file_name}行数错误，应为{row_num_exp}行')
        if col_num_exp is not None:
            if col_number != col_num_exp:
                error_list.append(f'{add_info}{in_file_name}行数错误，应为{row_num_exp}列')
        if len(error_list) == 0:
            return 0
        else:
            return error_list
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}快捷检查文件固定维度时出错", ]


@call_log
def check_file_line_fix(in_file, sep="\t", rm_blank=True, fill_null=False, null_list=None,
                        ck_row_fix=True, ck_col_fix=True, set_range=False,
                        range_min=1, range_max: int = None,
                        row_fix_no: int = 1, row_fix_content: list = (),
                        col_fix_no: int = 1, col_fix_content: list = (), add_info='', no_log=False):
    """
    数据固定行/列标题快捷检查，完整版使用 check_file_content，较完整版多出部分行/列内容固定的检查
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param sep: 字符串，分隔符，默认"\t"
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
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    try:
        if not os.path.isfile(in_file):
            return [f"{add_info}快捷检查文件固定内容时出错，文件{in_file}不存在或非文件", ]
        global min_index, max_index
        error_list = []
        if set_range:
            min_index = range_min - 1
        if set_range and range_max is not None:
            max_index = range_max - 1
        in_file_name = os.path.basename(in_file)
        if ck_row_fix and row_fix_content is not None:
            in_list = get_row2list(in_file=in_file, row_no=row_fix_no, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            if isinstance(row_fix_content, str):
                row_fix_content = [row_fix_content, ]
            if "max_index" not in vars():
                max_index = min_index + len(row_fix_content)
            if in_list[min_index:max_index] != list(row_fix_content):
                allowed_title = "\t".join(list(map(lambda x: str(x), row_fix_content)))
                if set_range:
                    msg = f"{add_info}{in_file_name}第{row_fix_no}行" \
                          f"第{range_min}至{max_index + 1}个元素必须为：{allowed_title}"
                    error_list.append(msg)
                else:
                    error_list.append(f"{add_info}{in_file_name}第{row_fix_no}行必须为：{allowed_title}")
        if ck_col_fix and col_fix_content is not None:
            in_list = get_col2list(in_file=in_file, col_no=col_fix_no, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            if isinstance(col_fix_content, str):
                col_fix_content = [col_fix_content, ]
            if "max_index" not in vars():
                max_index = min_index + len(col_fix_content)
            if in_list[min_index:max_index] != list(col_fix_content):
                allowed_title = "\t".join(list(map(lambda x: str(x), col_fix_content)))
                if set_range:
                    msg = f"{add_info}{in_file_name}第{row_fix_no}列" \
                          f"第{range_min}至{max_index + 1}个元素必须为：{allowed_title}"
                    error_list.append(msg)
                else:
                    error_list.append(f"{add_info}{in_file_name}第{row_fix_no}列必须为：{allowed_title}")
        if len(error_list) == 0:
            return 0
        else:
            return error_list
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}快捷检查文件固定内容时出错", ]


@call_log
def pre_check_file_content(in_file, out_dir, new_file=None, sep='\t', encoding="utf-8", add_info="", no_log=False):
    """
    文件详细内容检查预处理，自动消除BOM，注意new_file与in_file为同一文件时，处理后将会替换旧文件，已内置于check_file_content
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param out_dir: 字符串，处理后对象输出目录，推荐os.path.join(args.outdir,"tmp/analysis")
    :param new_file: 字符串，处理后对象名，将保存到out_dir目录下,默认与原文件同名
    :param sep: 字符串，分隔符，默认"\t"
    :param encoding: 字符串，输入及输出文件编码格式，不区分大小写,默认utf-8，不推荐修改
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回0，异常返回字符串报错信息
    """
    try:
        if not os.path.isfile(in_file):
            return f"{add_info}文件详细内容检查预处理时出错，文件{in_file}不存在或非文件"
        encoding = encoding.lower()
        in_file = os.path.abspath(in_file)
        if new_file is None:
            # new_file = os.path.abspath(in_file) + '.new'
            new_file = os.path.join(os.path.abspath(out_dir), os.path.basename(in_file))
        else:
            new_file = os.path.join(os.path.abspath(out_dir), os.path.basename(new_file))
            # new_file = os.path.join(os.path.dirname(os.path.abspath(in_file)), os.path.basename(new_file))  # 同路径
            # new_file = os.path.abspath(new_file)  # 自定路径
        if in_file == new_file:
            cmd = f'sed -i "/^\s*$/d" {new_file}'  # 去空白行
            print(cmd) if not no_log else 1
            os.system(cmd)
        else:
            cmd = f'mkdir -p {out_dir} && cp {in_file} {new_file} && sed -i "/^\s*$/d" {new_file}'  # 去空白行,仅限linux
            print(cmd) if not no_log else 1
            os.system(cmd)
        df = pd.read_csv(new_file, sep=sep, header=None, na_filter=False, encoding=encoding, quotechar=sep,
                         na_values="", keep_default_na=False)
        for i in range(df.shape[0]):  # 去元素前后空白
            for j in range(df.shape[1]):
                tem = str(df.iloc[i, j]).strip()
                df.iloc[i, j] = tem
        df.to_csv(new_file, sep=sep, index=0, header=None, quotechar=sep)
    except pd.errors.ParserError as e:
        print(e) if not no_log else 1
        list1 = str(e).strip().split(' ')
        return f"{add_info}[除空白行]首行包含{list1[-7]}列，而检测到第{list1[-3].strip(',')}行包含{list1[-1]}列，" \
               f"所有行的列数不应超过首行，请检查：1.是否在首行两个元素间有且只有一个分隔符[{sep}]2.第{list1[-3].strip(',')}行" \
               f"及后续行是否错误使用分隔符[{sep}]"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}文件详细内容检查预处理时出错"
    else:
        return 0


@call_log
def check_file_content(in_file, out_dir, new_file=None, pre_check=True,
                       sep="\t", rm_blank=True, fill_null=False, null_list=None,
                       ck_sep=False, sep_r=r'\t',
                       ck_header=False, ck_line_dup=False,
                       ck_row_num=True, ck_col_num=True,
                       row_num_exp: int = None, col_num_exp: int = None,
                       row_min_num_exp: int = None, col_min_num_exp: int = None,
                       row_max_num_exp: int = None, col_max_num_exp: int = None,
                       ck_row_base=True, ck_col_base=True,
                       ck_row_list: list = 1, ck_col_list: list = 1,
                       ck_row_length=True, ck_row_length_range=True,
                       ck_row_dup=True, ck_row_na=True, ck_row_ban=True,
                       ck_col_length=True, ck_col_length_range=True,
                       ck_col_dup=True, ck_col_na=True, ck_col_ban=True,
                       row_length: int = None, row_min_len=0, row_max_len: int = float('inf'),
                       col_length: int = None, col_min_len=0, col_max_len: int = float('inf'),
                       ban_list: list = None, na_list: list = None,
                       ck_row_fix=True, ck_col_fix=True,
                       row_fix_no: int = 1, col_fix_no: int = 1,
                       row_fix_content: list = None, col_fix_content: list = None,
                       ck_row_type=False, ck_col_type=False,
                       ck_row_type_list: list = None, ck_col_type_list: list = None,
                       exp_type='float', rm_first=False,
                       ck_row_num_range=False, ck_col_num_range=False,
                       row_min_num=float('-inf'), row_max_num=float('inf'),
                       col_min_num=float('-inf'), col_max_num=float('inf'),
                       ck_row_num_ban=True, ck_col_num_ban=True, ban_num: list = None,
                       ck_row_standard=False, ck_col_standard=False, ck_standard_list: list = None,
                       com_col_row_mum=True, row_greater: bool = None, contain_equal=True,
                       add_info='', no_log=False):
    """
    文件详细内容检查，注意new_file与in_file为同一文件时，处理后将会替换旧文件，后续检查及程序应使用new_file替代in_file传参
    :param in_file: 字符串，检查对象,例如："D:\a.txt"
    :param out_dir: 字符串，处理后对象输出目录，推荐os.path.join(args.outdir,"tmp/analysis")
    :param new_file: 字符串，处理后对象名，将保存到out_dir目录下,默认与原文件同名
    :param pre_check: 布尔值，是否调用pre_check_file_content进行预处理，默认True
    :param sep: 字符串，分隔符，默认"\t"
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
    :param row_min_len: 整数，基础检查，期望目标行长度下限，默认0
    :param row_max_len: 整数，基础检查，期望目标行长度上限，默认正无穷
    :param col_length: 整数，基础检查，期望目标列固定长度，None表示不检查，忽视ck_col_length
    :param col_min_len: 整数，基础检查，期望目标列长度下限，默认0
    :param col_max_len: 整数，基础检查，期望目标列长度上限，默认正无穷
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
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    try:
        if not os.path.isfile(in_file):
            return [f"{add_info}检查文件详细内容时出错，文件{in_file}不存在或非文件", ]
        error_list = []
        in_file_name = os.path.basename(in_file)
        if new_file is None:
            # new_file = os.path.abspath(in_file) + '.new'
            new_file = os.path.join(os.path.abspath(out_dir), os.path.basename(in_file))
        else:
            new_file = os.path.join(os.path.abspath(out_dir), os.path.basename(new_file))
            # new_file = os.path.join(os.path.dirname(os.path.abspath(in_file)), os.path.basename(new_file))  # 同路径
        if pre_check:
            err_msg = pre_check_file_content(in_file, out_dir=out_dir, new_file=new_file, sep=sep, encoding='utf-8',
                                             no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}输入文件{in_file_name}{err_msg}")
                return error_list
        in_file = new_file  # 分隔符检查前，需确保使用去除空行及元素前后空白的新文件
        row_number = get_row_num(in_file=in_file, no_log=no_log)
        col_number = get_col_num(in_file=in_file, sep=sep, no_log=no_log)
        if ck_sep:
            for row in range(1, row_number + 1):
                in_line = get_row_line(in_file=in_file, line_num=row, no_log=True)
                err_msg = line_sep(in_line, sep_r=sep_r, no_log=True)
                if err_msg:
                    error_list.append(f"{add_info}输入文件{in_file_name}第{row}行{err_msg}")
        if ck_header:
            in_list = get_row2list(in_file=in_file, row_no=1, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            tail_length = get_col_num(in_file=in_file, sep=sep, no_log=no_log)
            if len(in_list) < tail_length:
                msg = f"{add_info}输入文件{in_file_name}的首行（标题行）部分为空，无法识别标题，请检查是否在两个行名间有且只有一个分隔符"
                error_list.append(msg)
        if ck_line_dup:
            err_msg = file_line_dup(in_file=in_file, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}输入文件{in_file_name}{err_msg}")
        if error_list:  # 维度检查前需确保分隔符正确
            return error_list
        if ck_row_num and row_num_exp is not None:
            in_list = get_col2list(in_file=in_file, col_no=1, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            err_msg = list_length(in_list=in_list, exp_len=row_num_exp, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}输入文件{in_file_name}行数有误：{err_msg}")
        if ck_col_num and col_num_exp is not None:
            in_list = get_row2list(in_file=in_file, row_no=1, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            err_msg = list_length(in_list=in_list, exp_len=col_num_exp, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}输入文件{in_file_name}列数有误：{err_msg}")
        if ck_row_num and row_num_exp is None and (row_min_num_exp or row_max_num_exp) is not None:
            if row_min_num_exp is None:
                row_min_num_exp = 1
            if row_max_num_exp is None:
                row_max_num_exp = float('inf')
            in_list = get_col2list(in_file=in_file, col_no=1, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            err_msg = list_length(in_list=in_list, min_len=row_min_num_exp, max_len=row_max_num_exp, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}输入文件{in_file_name}行数范围有误：{err_msg}")
        if ck_col_num and col_num_exp is None and (col_min_num_exp or col_max_num_exp) is not None:
            if col_min_num_exp is None:
                col_min_num_exp = 1
            if col_max_num_exp is None:
                col_max_num_exp = float('inf')
            in_list = get_row2list(in_file=in_file, row_no=1, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            err_msg = list_length(in_list=in_list, min_len=col_min_num_exp, max_len=col_max_num_exp, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}输入文件{in_file_name}列数范围有误：{err_msg}")
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
                in_list = get_row2list(in_file=in_file, row_no=row, sep=sep, rm_blank=rm_blank,
                                       fill_null=fill_null, null_list=null_list, no_log=True)
                if ck_row_length and row_length is not None:
                    err_msg = list_length(in_list=in_list, exp_len=row_length, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{row}行{err_msg}")
                elif not ck_row_length and ck_row_length_range:
                    err_msg = list_range(in_list=in_list, min_len=row_min_len, max_len=row_max_len, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{row}行{err_msg}")
                if ck_row_dup:
                    err_msg = list_dup(in_list=in_list, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{row}行有重复：{err_msg}，该行不允许重复值")
                if ck_row_ban and ban_list is not None:
                    err_msg = list_ban(in_list=in_list, ban_list=ban_list, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{row}行检查到非法元素{err_msg}")
                if ck_row_na:
                    err_msg = list_na(in_list=in_list, na_list=na_list, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{row}行{err_msg}")
        if ck_col_base:
            if ck_col_list == -1:
                ck_col_list = range(2, col_number + 1)
            elif ck_col_list is None or ck_col_list == 0:
                ck_col_list = range(1, col_number + 1)
            if isinstance(ck_col_list, int):
                ck_col_list = [ck_col_list, ]
            for col in ck_col_list:
                in_list = get_col2list(in_file=in_file, col_no=col, sep=sep, rm_blank=rm_blank,
                                       fill_null=fill_null, null_list=null_list, no_log=True)
                if ck_col_length and col_length is not None:
                    err_msg = list_length(in_list=in_list, exp_len=col_length, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{col}列{err_msg}")
                elif not ck_col_length and ck_col_length_range:
                    err_msg = list_range(in_list=in_list, min_len=col_min_len, max_len=col_max_len, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{col}列{err_msg}")
                if ck_col_dup:
                    err_msg = list_dup(in_list=in_list, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{col}列有重复：{err_msg}，该列不允许重复值")
                if ck_col_ban and ban_list is not None:
                    err_msg = list_ban(in_list=in_list, ban_list=ban_list, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{col}列检查到非法元素{err_msg}")
                if ck_col_na:
                    err_msg = list_na(in_list=in_list, na_list=na_list, no_log=True)
                    if err_msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{col}列{err_msg}")
        if ck_row_fix and row_fix_content is not None:
            in_list = get_row2list(in_file=in_file, row_no=row_fix_no, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            if isinstance(row_fix_content, str):
                row_fix_content = [row_fix_content, ]
            if in_list != list(row_fix_content):
                in_title = ",".join(map(lambda x: str(x), in_list))
                allowed_title = ",".join(map(lambda x: str(x), row_fix_content))
                err_msg = f"{add_info}输入文件{in_file_name}第{row_fix_no}行为{in_title}，该行必须为{allowed_title}，请检查"
                error_list.append(err_msg)
        if ck_col_fix and col_fix_content is not None:
            in_list = get_col2list(in_file=in_file, col_no=col_fix_no, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=no_log)
            if isinstance(col_fix_content, str):
                col_fix_content = [col_fix_content, ]
            if in_list != list(col_fix_content):
                in_title = ",".join(map(lambda x: str(x), in_list))
                allowed_title = ",".join(map(lambda x: str(x), col_fix_content))
                err_msg = f"{add_info}输入文件{in_file_name}第{col_fix_no}列为{in_title}，该列必须为{allowed_title}，请检查"
                error_list.append(err_msg)
        row_flag = []
        if ck_row_type:
            if ck_row_type_list == -1:
                ck_row_type_list = range(2, row_number + 1)
            elif ck_row_type_list is None or ck_row_type_list == 0:
                ck_row_type_list = range(1, row_number + 1)
            if isinstance(ck_row_type_list, int):
                ck_row_type_list = [ck_row_type_list, ]
            for row in ck_row_type_list:
                in_list = get_row2list(in_file=in_file, row_no=row, sep=sep, rm_blank=rm_blank,
                                       fill_null=fill_null, null_list=null_list, no_log=True)
                msg = list_type(in_list=in_list, exp_type=exp_type, rm_first=rm_first, no_log=True)
                if isinstance(msg, str):
                    error_list.append(f"{add_info}输入文件{in_file_name}第{row}行{msg}")
                else:
                    if exp_type in ['float', 'int']:
                        row_flag.append(1)
                    if ck_row_num_range:
                        err_msg = list_num_range(in_list=msg, min_num=row_min_num, max_num=row_max_num, no_log=True)
                        if err_msg:
                            error_list.append(f"{add_info}输入文件{in_file_name}第{row}行{err_msg}")
                    if ck_row_num_ban and ban_num is not None:
                        err_msg = list_num_ban(in_list=msg, ban_num=ban_num, no_log=True)
                        if err_msg:
                            error_list.append(f"{add_info}输入文件{in_file_name}第{row}行{err_msg}")
        col_flag = []
        if ck_col_type:
            if ck_col_type_list == -1:
                ck_col_type_list = range(2, col_number + 1)
            elif ck_col_type_list is None or ck_col_type_list == 0:
                ck_col_type_list = range(1, col_number + 1)
            if isinstance(ck_col_type_list, int):
                ck_col_type_list = [ck_col_type_list, ]
            for col in ck_col_type_list:
                in_list = get_col2list(in_file=in_file, col_no=col, sep=sep, rm_blank=rm_blank,
                                       fill_null=fill_null, null_list=null_list, no_log=True)
                msg = list_type(in_list=in_list, exp_type=exp_type, rm_first=rm_first, no_log=True)
                if isinstance(msg, str):
                    error_list.append(f"{add_info}输入文件{in_file_name}第{col}列{msg}")
                else:
                    if exp_type in ['float', 'int']:
                        col_flag.append(1)
                    if ck_col_num_range:
                        err_msg = list_num_range(in_list=msg, min_num=col_min_num, max_num=col_max_num, no_log=True)
                        if err_msg:
                            error_list.append(f"{add_info}输入文件{in_file_name}第{col}列{err_msg}")
                    if ck_col_num_ban and ban_num is not None:
                        err_msg = list_num_ban(in_list=msg, ban_num=ban_num, no_log=True)
                        if err_msg:
                            error_list.append(f"{add_info}输入文件{in_file_name}第{col}列{err_msg}")
        if row_flag and ck_row_standard:
            if ck_standard_list == -1:
                ck_standard_list = range(2, row_number + 1)
            elif ck_standard_list is None:
                ck_standard_list = range(1, row_number + 1)
            if isinstance(ck_standard_list, int):
                ck_standard_list = [ck_standard_list, ]
            if ck_standard_list in ck_row_type_list:
                for row in ck_standard_list:
                    in_list = get_row2list(in_file=in_file, row_no=row, sep=sep, rm_blank=rm_blank,
                                           fill_null=fill_null, null_list=null_list, no_log=True)
                    msg = list_factor(in_list=in_list, exp_num=1, rm_first=rm_first, no_log=True)
                    if not msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{row}行数据完全一致，"
                                          f"标准差为0，不能按行进行标准化，请删除该行或尝试按列标准化")
        if col_flag and ck_col_standard:
            if ck_standard_list == -1:
                ck_standard_list = range(2, col_number + 1)
            elif ck_standard_list is None:
                ck_standard_list = range(1, col_number + 1)
            if isinstance(ck_standard_list, int):
                ck_standard_list = [ck_standard_list, ]
            if ck_standard_list in ck_col_type_list:
                for col in ck_standard_list:
                    in_list = get_col2list(in_file=in_file, col_no=col, sep=sep, rm_blank=rm_blank,
                                           fill_null=fill_null, null_list=null_list, no_log=True)
                    msg = list_factor(in_list=in_list, exp_num=1, rm_first=rm_first, no_log=True)
                    if not msg:
                        error_list.append(f"{add_info}输入文件{in_file_name}第{col}列数据完全一致，"
                                          f"标准差为0，不能按列进行标准化，请删除该列或尝试按行标准化")
        if com_col_row_mum and row_greater is not None:
            err_msg = file_com_row_col_num(in_file=in_file, sep=sep, row_greater=row_greater,
                                           contain_equal=contain_equal, no_log=no_log)
            if err_msg:
                error_list.append(f"{add_info}输入文件{in_file_name}{err_msg}")
        if len(error_list) == 0:
            return 0
        else:
            return error_list
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}检查文件详细内容时出错", ]


@call_log
def com_list(list1: list, list2: list, order_strict=False, rm_first=False,
             ck_1_in_2=False, key='元素', add_info="", no_log=False):
    """
    比较两个列表元素是否相同
    :param list1: 列表，第一个比较对象
    :param list2: 列表，第二个比较对象
    :param order_strict: 布尔值，是否严格顺序比较，默认False,即不考虑元素顺序
    :param rm_first: 布尔值，是否移除首个元素，默认False
    :param ck_1_in_2: 布尔值，是否检查list1是否包含于list2，默认False，即仅寻找互斥元素
    :param key: 字符串，关键字信息，默认'元素'
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 相同返回0，不同返回字符串报错信息
    """
    try:
        if rm_first:
            list1 = list1[1:]
            list2 = list2[1:]
        if order_strict:
            other = ''
            err = []
            if ck_1_in_2 and len(list1) > len(list2):
                other += f'，且存在超出的{key}'
            elif not ck_1_in_2 and len(list1) != len(list2):
                other += "，且长度不同"
            n = min(len(list1), len(list2))
            for i in range(1, n + 1):
                if list1[i - 1] != list2[i - 1]:
                    # err.append(i)  # 报元素位置
                    err.append(list1[i - 1])  # 报元素名
            if len(err) != 0:
                # msg = f"{add_info}发现不同{key}，分别为第{_join_str(err)}个{other} "  # 报元素位置
                msg = f"{add_info}发现不同{key}，分别为{_join_str(err)}{other} "  # 报元素名
                return msg
            else:
                return 0
        else:
            set1 = set(list1)
            set2 = set(list2)
            diff_items = list(set1.symmetric_difference(set2))
            if not diff_items:
                return 0
            diff1 = list(set1.difference(set2))
            if ck_1_in_2 and diff1:
                return f"{add_info}发现多出的{key}，分别为{_join_str(diff1)}"
            elif not ck_1_in_2:
                diff2 = list(set2.difference(set1))
                return f"{add_info}发现不同的{key}，分别为:{_join_str(diff1)};{_join_str(diff2)}。"
            else:
                return 0
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}比较两列表内容时出错"


@call_log
def check_com_line(in_file1, in_file2,
                   ck_1_row: bool = None, ck_1_col: bool = None,
                   ck_2_row: bool = None, ck_2_col: bool = None,
                   file1_no=1, file2_no=1,
                   order_strict=False, rm_first=False, ck_1_in_2=False,
                   sep="\t", rm_blank=True, fill_null=False, null_list=None, key='样本', add_info="", no_log=False):
    """
    对比两个文件某一行/列数据的差异
    :param in_file1: 字符串，检查对象1,例如："D:\a.txt"
    :param in_file2: 字符串，检查对象2,例如："D:\b.txt"
    :param ck_1_row: 布尔值，是否检查对象1的行，与ck_1_col有且必需有一个需要提供True
    :param ck_1_col: 布尔值，是否检查对象1的列，与ck_1_row有且必需有一个需要提供True
    :param ck_2_row: 布尔值，是否检查对象2的行，与ck_2_col有且必需有一个需要提供True
    :param ck_2_col: 布尔值，是否检查对象2的列，与ck_2_row有且必需有一个需要提供True
    :param file1_no: 正整数，检查对象1要检查的行/列号，默认1
    :param file2_no: 正整数，检查对象2要检查的行/列号，默认1
    :param order_strict: 布尔值，是否严格顺序比较，默认False，即不考虑元素顺序
    :param rm_first: 布尔值，是否移除首个元素，默认False
    :param ck_1_in_2: 布尔值，是否检查list1是否包含于list2，默认False，即仅寻找互斥元素
    :param sep: 字符串，分隔符，默认"\t"
    :param rm_blank: 布尔值，是否移除该列元素前后空白，默认True
    :param fill_null: 布尔值，是否将缺失数据统一替换为NA，默认True
    :param null_list: 字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
    :param key: 字符串，关键字信息，默认'样本'
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    try:
        global in_list1, in_list2
        if ck_1_row and ck_1_col:
            print('文件1仅接受一个维度')
        if ck_2_row and ck_2_col:
            print('文件2仅接受一个维度')
        if not (ck_1_row or ck_1_col):
            print('文件1需指定一个维度')
        if not (ck_2_row or ck_2_col):
            print('文件2需指定一个维度')
        if not os.path.isfile(in_file1):
            return [f"{add_info}比较两文件内容时出错，文件{in_file1}不存在或非文件", ]
        if not os.path.isfile(in_file2):
            return [f"{add_info}比较两文件内容时出错，文件{in_file2}不存在或非文件", ]
        dim1 = "行" if ck_1_row else "列"
        dim2 = "行" if ck_2_row else "列"
        in_file_name1 = os.path.basename(in_file1)
        in_file_name2 = os.path.basename(in_file2)
        if (ck_1_row or ck_1_col) and (not (ck_1_row and ck_1_col)) \
                and (ck_2_row or ck_2_col) and (not (ck_2_row and ck_2_col)):
            if ck_1_row:
                in_list1 = get_row2list(in_file=in_file1, row_no=file1_no, sep=sep, rm_blank=rm_blank,
                                        fill_null=fill_null, null_list=null_list, no_log=True)
            if ck_1_col:
                in_list1 = get_col2list(in_file=in_file1, col_no=file1_no, sep=sep, rm_blank=rm_blank,
                                        fill_null=fill_null, null_list=null_list, no_log=True)
            if ck_2_row:
                in_list2 = get_row2list(in_file=in_file2, row_no=file2_no, sep=sep, rm_blank=rm_blank,
                                        fill_null=fill_null, null_list=null_list, no_log=True)
            if ck_2_col:
                in_list2 = get_col2list(in_file=in_file2, col_no=file2_no, sep=sep, rm_blank=rm_blank,
                                        fill_null=fill_null, null_list=null_list, no_log=True)
            msg = com_list(list1=in_list1, list2=in_list2, order_strict=order_strict, rm_first=rm_first,
                           ck_1_in_2=ck_1_in_2, key=key, no_log=no_log)
            if msg != 0:
                return f'{add_info}{in_file_name1}第{file1_no}{dim1}与{in_file_name2}第{file2_no}{dim2}{msg}'
            else:
                return 0
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}比较两文件内容时出错", ]


@call_log
def check_str_in_file_line(in_str, in_file, ck_row=True, ck_col=True, row_no: int = None, col_no: int = None,
                           sep="\t", rm_blank=True, fill_null=False, null_list=None, add_info="", no_log=False):
    """
    检查（参数等）字符串/字符串列表是否（全部）包含在文件某行中
    :param in_str: 字符串/字符串列表，检查对象字符串
    :param in_file: 字符串，检查对象文件,例如："D:\a.txt"
    :param ck_row: 布尔值，是否检查某行，默认True
    :param ck_col: 布尔值，是否检查某列，默认True
    :param row_no: 正整数，检查行行号，None表示不检查行，忽视ck_row
    :param col_no: 正整数，检查列列号，None表示不检查列，忽视ck_col
    :param sep: 字符串，分隔符，默认"\t"
    :param rm_blank: 布尔值，移除该列元素前后空白，默认True
    :param fill_null: 布尔值，将缺失数据统一替换为NA，默认True
    :param null_list: 字符串列表，指定原数据表示缺失数据的符号，默认["", "NA", "N/A", "NULL"]
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合返回报错信息列表
    """
    try:
        if not os.path.isfile(in_file):
            return [f"{add_info}检查文件包含字符串时，检查文件{in_file}不存在或非文件", ]
        global in_str_list
        if isinstance(in_str, str):
            in_str_list = [in_str, ]
        in_file_name = os.path.basename(in_file)
        error_list = []
        if ck_row and row_no is not None:
            in_list = get_row2list(in_file=in_file, row_no=row_no, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=True)
            in_list = list(map(lambda x: str(x), in_list))
            in_str_list = list(map(lambda x: str(x), in_str_list))
            str_item = set(in_str_list).difference(set(in_list))
            if str_item:
                error_list.append(f"{add_info}{in_file_name}第{row_no}行不含{_join_str(str_item)}元素")
        if ck_col and col_no is not None:
            in_list = get_col2list(in_file=in_file, col_no=col_no, sep=sep, rm_blank=rm_blank,
                                   fill_null=fill_null, null_list=null_list, no_log=True)
            in_list = list(map(lambda x: str(x), in_list))
            in_str_list = list(map(lambda x: str(x), in_str_list))
            str_item = set(in_str_list).difference(set(in_list))
            if str_item:
                error_list.append(f"{add_info}{in_file_name}第{col_no}列不含{_join_str(str_item)}元素")
        if len(error_list) != 0:
            return error_list
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}检查文件包含字符串时出错", ]


@call_log
def del_all(path, self_contain=False, add_info="", no_log=False):
    """
    删除指定目录下所有内容（包含文件及文件夹，默认不包含自身）
    :param path: 字符串，指定目录，推荐绝对路径
    :param self_contain: 布尔值，是否删除path自身，默认False
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 删除成功无返回，删除失败返回字符串报错信息
    """
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
        print(e) if not no_log else 1
        return f"{add_info}删除文件夹{path}时出错"


dir_del_all = dir_del = del_all


@call_log
def make_dir(path, del_old=True, add_info='', no_log=False):
    """
    创建目录(注意：该函数默认会删除已存在目录下所有内容)
    :param path: 字符串，创建的文件夹名称，推荐绝对路径
    :param del_old: 布尔值，是否删除已存在目录及其中文件（夹）并重建目录，默认True
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 创建成功无返回，创建失败返回字符串报错信息
    """
    try:
        path = _path_pre_proc(path)
        if os.path.exists(path):
            if del_old:
                del_all(path)
        else:
            os.makedirs(path)
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}无法创建目录{path}"


@call_log
def copy_file(in_file, path, new_file=None, add_info='', no_log=False):
    """
    复制文件到目标路径下
    :param in_file: 字符串，复制文件，要复制的文件名称
    :param path: 字符串，复制文件的目标文件夹名称，推荐绝对路径，如路径不存在，将创建该路径
    :param new_file: 字符串，目标文件，复制后的文件名称，None表示与原文件同名
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 成功返回0，失败返回字符串报错信息
    """
    try:
        in_file = os.path.abspath(in_file)
        if os.path.isfile(in_file):
            if new_file is None:
                new_file = os.path.basename(in_file)
            new_file = os.path.join(os.path.abspath(path), os.path.basename(new_file))
            if in_file == new_file:
                return f"{add_info}复制文件与目标文件为同一文件{in_file}"
            if not os.path.exists(path):
                os.makedirs(path)
            shutil.copyfile(in_file, new_file)
            return 0
        else:
            return f"{add_info}复制文件不存在或非文件{in_file}"
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}复制文件时出错"


@call_log
def make_cloud_dir(path, more=True, more_dir: list = None, add_info='', no_log=False):
    """
    创建云平台 v2.0 结果目录树
    :param path: 字符串，创建结果目录树的路径（tmp父级目录），推荐绝对路径
    :param more: 布尔值，是否需要额外创建分析分析文件夹,默认True
    :param more_dir: 字符串/字符串列表，创建额外分析文件夹的名称，默认创建 analysis 文件夹
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 创建成功无返回，创建失败返回字符串报错信息
    """
    try:
        path = _path_pre_proc(path)
        abs_path = os.path.abspath(path)
        tmp_dir = os.path.join(abs_path, "tmp")
        err_msg = make_dir(tmp_dir, no_log=no_log)
        if err_msg:
            return f'{add_info}{err_msg}'
        res_dir = os.path.join(tmp_dir, "cloud_result")
        err_msg = make_dir(res_dir, no_log=no_log)
        if err_msg:
            return f'{add_info}{err_msg}'
        err_dir = os.path.join(tmp_dir, "cloud_error")
        err_msg = make_dir(err_dir, no_log=no_log)
        if err_msg:
            return f'{add_info}{err_msg}'
        svg_dir = os.path.join(tmp_dir, "cloud_svg")
        err_msg = make_dir(svg_dir, no_log=no_log)
        if err_msg:
            return f'{add_info}{err_msg}'
        if more:
            if more_dir is None:
                more_dir = 'analysis'
            if isinstance(more_dir, str):
                more_dir = [more_dir, ]
            for i_dir in more_dir:
                ana_dir = os.path.join(tmp_dir, i_dir)
                err_msg = make_dir(ana_dir, no_log=no_log)
                if err_msg:
                    return f'{add_info}{err_msg}'
    except Exception as e:
        print(e) if not no_log else 1
        return f"{add_info}创建结果目录树时出错"


@call_log
def check_dir_item(path, exp_item: list = None, ck_null=True, add_info='', no_log=False):
    """
    文件夹目录内容检查(存在，空文件)
    :param path: 字符串，检查目录路径，推荐绝对路径
    :param exp_item: 字符串/字符串列表，期望存在的文件列表，None表示将path文件夹内容全部检查
    :param ck_null: 布尔值，是否检查空文件，默认True
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 符合期望返回0，不符合期望返回报错信息列表
    """
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
                    msg = file_null(os.path.join(path, i_exp), no_log=no_log)
                    if msg:
                        null_item.append(i_exp)
        if len(have_item) == 0:
            return [f'{add_info}检测不到结果文件，请检查', ]
        elif len(no_item) != 0 and len(null_item) == 0:
            return [f'{add_info}检测不到结果文件：{_join_str(no_item)}，请检查', ]
        elif len(no_item) != 0 and len(null_item) != 0:
            return [f'{add_info}检测不到结果文件：{_join_str(no_item)}且以下结果文件为空：{_join_str(null_item)}', ]
        elif len(no_item) == 0 and len(null_item) != 0:
            return [f'{add_info}检测到以下结果文件为空：{_join_str(null_item)}', ]
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}检查结果文件时出错", ]


def dir_size(path, exp_item, add_info='', no_log=False):
    """搁置，已有空文件检查、单文件大小检查、批量空文件检查，文件大小批量检查意义不大"""
    pass


@call_log
def make_result(path, out_dir, exp_item=None,
                out2zip='result.zip', out2json: str = None, add_info='', no_log=False):
    """
    创建结果文件压缩包并将压缩包(及json)文件移至云平台2.0要求存储目录
    :param path: 字符串，数据分析结果临时储存目录，推荐绝对路径
    :param out_dir: 字符串，结果存储文件夹(tmp文件夹的父级目录)
    :param exp_item: 字符串/字符串列表，path目录中要打包进压缩包的结果文件[夹](文件夹将会被遍历，文件含后缀)，
        None表示将path文件夹内容全部打包
    :param out2zip: 字符串，结果文件压缩包名称(含后缀)，V2.0要求固定为 result.zip，不建议修改此项
    :param out2json: 字符串，path目录下json结果文件名称(含后缀),None表示无json文件需要转移
    :param add_info: 字符串，附加信息
    :param no_log: 不打印调用及报错信息，默认为False
    :return: 正常返回0，错误返回报错信息列表
    """
    try:
        path = _path_pre_proc(path)
        path = os.path.abspath(path)
        if exp_item is None:
            exp_item = os.listdir(path)
        if isinstance(exp_item, str):
            exp_item = [exp_item, ]
        if exp_item is None:
            exp_item = os.listdir(path)
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
            print(e) if not no_log else 1
            err_msg = f"{add_info}压缩结果文件时发生错误"
            error_list.append(err_msg)
        try:
            res_file = os.path.join(out_dir, 'tmp/cloud_result', base_name)
            shutil.copyfile(out2zip, res_file)
        except Exception as e:
            print(e) if not no_log else 1
            err_msg = f"{add_info}复制压缩结果文件时发生错误"
            error_list.append(err_msg)
        if out2json:
            base_name = os.path.basename(out2json)
            out2json = os.path.join(path, base_name)
            try:
                res_file = os.path.join(out_dir, 'tmp/cloud_svg', base_name)
                shutil.copyfile(out2json, res_file)
            except Exception as e:
                print(e) if not no_log else 1
                err_msg = f"{add_info}复制json结果时发生错误"
                error_list.append(err_msg)
        if error_list:
            return error_list
        else:
            return 0
    except Exception as e:
        print(e) if not no_log else 1
        return [f"{add_info}结果文件压缩拷贝时出错", ]


@call_log
def write_log(log_list, log_file, no_log=False):
    """
    日志/报错等信息列表记录到文件
    :param log_list: 字符串/字符串列表，待记录对象
    :param log_file: 字符串，记录文件名称,例如："D:\a.txt"
    :param no_log: 不打印调用及报错信息，默认为False
    :return:
    """
    if isinstance(log_list, str):
        log_list = [log_list, ]
    with codecs.open(log_file, "w", encoding="UTF-8") as log:
        if not no_log:
            log.write("很抱歉您的任务运行失败，原因是在您的输入文件里发现存在以下问题，请根据问题描述结合工具的详细说明进行修改后重新投递：\n")
        for i_log in log_list:
            i_log = ">>> " + i_log + "\n"
            log.write(i_log)


@call_log
def write_default_log(log_file, no_log=False):
    """生成默认报错文档"""
    err_msg = ("程序存在意外的错误，请联系技术支持从后台进行问题排查\n"
               "\t技术支持邮箱：cloudsupport@metware.cn")
    write_log(log_list=err_msg, log_file=log_file, no_log=no_log)


if __name__ == "__main__":
    sys.stderr.write("This is a check module.  ")
    sys.exit(1)
