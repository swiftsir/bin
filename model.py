#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
main script for [   ]
@author: WangMing
"""
# ---- ---- ---- ---- ---- #
import argparse
import time
import os
import sys
import re
import pandas as pd
import numpy as np

# sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin"))
# import check as c


# from bin import check as c  # windows
# from .bin import check as c  # windows


from checkdir import check as c  # windows for me


def basic_options():
    parser = argparse.ArgumentParser(usage="python3 %(prog)s",
                                     description="[ ]",
                                     add_help=True)
    parser.add_argument("-i", "--infile", required=True, dest="infile",
                        help="File name of infile data. [must be specified]",
                        type=str, nargs='?', action="store")
    parser.add_argument("-g", "--groupfile", required=True, dest="groupfile",
                        help="File name of groupfile data. [must be specified]",
                        type=str, nargs='?', action="store")
    parser.add_argument('-o', '--outdir', required=False, dest="outdir",
                        help="Directory of working directory. Optional, [default: %(default)s]",
                        type=str, nargs='?', default="./")
    parser.add_argument('-pre', '--prefix', required=False, dest="prefix",
                        help="Prefix of output files. Optional, [default: %(default)s]",
                        type=str, nargs='?', default="result")
    parser.add_argument('-str', '--str', required=False, dest="str",
                        help="[ ]. Optional, [ default: %(default)s]",
                        type=str, nargs='?', default="FALSE",
                        choices=("FALSE", "TRUE"))
    parser.add_argument('-int', '--int', required=False, dest="int",
                        help="[ ]. Optional, [default: %(default)s]",
                        type=int, nargs='?', default=1000)
    parser.add_argument('-float', '--float', required=False, dest="float",
                        help="[ ]. Optional, [default: %(default)s]",
                        type=float, nargs='?', default=0.01)

    return parser


def main(in_parser):
    # ---- ---- ---- ---- ---- #
    # pre check
    global run_cmd
    args, unparsed = in_parser.parse_known_args()
    prefix = args.prefix
    outDir = os.path.abspath(args.outdir)
    infile = os.path.abspath(args.infile)
    newinfile = os.path.join(os.path.join(outDir, "tmp/tmp_data"), os.path.basename(infile))
    groupfile = os.path.abspath(args.groupfile)
    newgroupfile = os.path.join(os.path.join(outDir, "tmp/tmp_data"), os.path.basename(groupfile))
    c.make_cloud_dir(outDir, more_dir=['analysis', 'tmp_data'])
    bin_path = os.path.dirname(os.path.abspath(__file__)) + "/bin"
    ana_path = os.path.join(outDir, 'tmp/analysis')
    dat_path = os.path.join(outDir, 'tmp/tmp_data')
    log_file = f"{outDir}/tmp/cloud_error/error.txt"
    c.write_default_log(log_file)
    perl = os.popen('which perl').read().rstrip('\n')
    Rscript = os.popen('which Rscript').read().rstrip('\n')
    python3 = os.popen('which python3').read().rstrip('\n')
    # python = os.popen('which python').read().rstrip('\n')
    # ---- ---- ---- ---- ---- #
    # check
    err_log = []
    # check str
    msg_list = c.check_str(args.prefix, add_info='输出文件前缀：')
    if msg_list:
        err_log.extend(msg_list)
    # check num
    msg_list = c.check_num(args.int, min_num=1000, max_num=10000000, add_info='[ ]：')
    if msg_list:
        err_log.extend(msg_list)
    # check file
    # check infile
    err_plus = []
    msg_list = c.check_file_base(in_file=infile, out_file=newinfile)
    if msg_list:
        err_plus.extend(msg_list)
    if len(err_plus) < 1:
        # 删除所有空白行及元素前后空格，在out_dir生成检查后同名新文档；检查文件列数至少为5
        # 除第一列，检查所有列无缺失，为浮点数；（默认）检查第一行无重复缺失
        msg_list = c.check_file_content(in_file=newinfile, out_dir=dat_path,
                                        col_min_num_exp=5, ck_col_base=True, ck_col_dup=False, ck_col_list=-1,
                                        ck_col_type=True, ck_col_type_list=-1, exp_type="float", rm_first=True,
                                        add_info='输入文件：')
        if msg_list:
            err_plus.extend(msg_list)
    if not err_plus:
        col_list = c.get_col2list(in_file=newinfile, col_no=1)
        add_info = "输入文件Index列"
        if col_list[0] != "Index":
            add_info = f"输入文件{col_list[1]}列"
            if True:  # 当无固定列名检查，但要求第一类列名固定为"Index"时，设置为True
                err_plus.append(f"{add_info}列名错误，该列要求固定为Index")
        err_msg = c.list_dup(col_list[1:], key="名称", add_info=add_info)
        if err_msg:  # 单独检查第一列重复
            err_plus.append(err_msg)
        err_msg = c.list_format(in_list=col_list[1:], key="名称", add_info=add_info)
        if err_msg:  # 单独检查第一列字符串为数字、字母、点号（“.”）、下划线（“_”）和中划线（“-”）的组合，并且必须以字母或数字开头
            err_plus.append(err_msg)
        if not err_plus:
            df = pd.read_csv(newinfile, sep="\t", header=0, index_col=0)
            ndf = df[np.var(df, axis=1) != 0]
            if ndf.shape[0] < 4:
                err_plus.append(f"输入文件：代谢物数目错误，删除表达量一致的代谢物后剩余代谢物数为{ndf.shape[0]},不足4个")
            ndf.to_csv(newinfile, sep="\t", index=True, header=True)

    # check groupfile
    err_plus2 = []
    msg_list = c.check_file_base(in_file=groupfile, out_file=newgroupfile)
    if msg_list:
        err_plus2.extend(msg_list)
    if len(err_plus2) < 1:
        # 删除所有空白行及元素前后空格，在out_dir生成检查后同名新文档；检查重复行；检查列数为2；检查1、2列无缺失；（默认）检查第一行无重复缺失；
        # 检查第一行(默认)固定内容为"Index", "Group"
        msg_list = c.check_file_content(in_file=newgroupfile, out_dir=dat_path,
                                        ck_line_dup=True, col_num_exp=2, ck_col_list=[1, 2], ck_col_dup=False,
                                        row_fix_content=["Index", "Group"],
                                        add_info='分组文件：')
        if msg_list:
            err_plus2.extend(msg_list)
    if not err_plus2:
        col_list = c.get_col2list(in_file=newgroupfile, col_no=1)
        err_msg = c.list_dup(col_list[1:], key="名称", add_info="分组文件Index列：")
        if err_msg:  # 单独检查第一列重复
            err_plus2.append(err_msg)
        err_msg = c.list_format(in_list=col_list[1:], key="名称", add_info="分组文件Index列：")
        if err_msg:  # 单独检查第一列字符串为数字、字母、点号（“.”）、下划线（“_”）和中划线（“-”）的组合，并且必须以字母或数字开头
            err_plus2.append(err_msg)
        col_list = c.get_col2list(in_file=newgroupfile, col_no=2)
        err_msg = c.list_format(in_list=col_list[1:], key="名称", add_info="分组文件Group列：")
        if err_msg:  # 单独检查第二列字符串为数字、字母、点号（“.”）、下划线（“_”）和中划线（“-”）的组合，并且必须以字母或数字开头
            err_plus2.append(err_msg)
    if not err_plus and not err_plus2:
        err_msg = c.check_com_line(in_file1=newinfile, in_file2=newgroupfile, ck_1_row=True, ck_2_col=True,
                                   rm_first=True, add_info="输入文件与分组文件样品名不匹配：")
        if err_msg:
            err_plus2.append(err_msg)
    condition = "[  ]"
    work_type = ""
    if condition:
        work_type = "a"
    elif not condition:
        work_type = "b"
    else:
        err_plus.append("[ ]")
    err_log = err_log + err_plus + err_plus2
    # ---- ---- ---- ---- ---- #
    # after check
    if err_log:
        print(err_log)
        c.write_log(log_list=err_log, log_file=log_file)
        sys.exit(1)
    # run proc
    a_path = os.path.dirname(os.path.abspath(__file__)) + "/a"
    b_path = os.path.dirname(os.path.abspath(__file__)) + "/b"
    c_path = os.path.dirname(os.path.abspath(__file__)) + "/c"
    if work_type == "a":
        run_cmd = f"{perl} {a_path}/[ ].pl --infile {newinfile} "
    elif work_type == "b":
        run_cmd = f"{Rscript} {b_path}/[].R --infile {newinfile} "
    else:
        run_cmd = f"{python3} {c_path}/[].py --infile {newinfile} "
    run_cmd = f"{Rscript} {bin_path}/[ ].R --infile {newinfile} --groupfile {newgroupfile} --outdir {outDir}  " \
              f"--outPrefix {prefix} --ell {args.ell} --scale {args.scale} --label {args.label} " \
              f"--height {args.height} --width {args.width}"
    print(run_cmd)
    p1 = os.system(run_cmd)
    if p1 == 0:
        msg_list = c.check_dir_item(ana_path,
                                    exp_item=["[ ]", "[ ]"])
        if msg_list:
            err_log.extend(msg_list)
        else:
            msg_list = c.make_result(ana_path, out_dir=outDir, exp_item=["[ ]", "[ ]"])
            if msg_list:
                err_log.extend(msg_list)
        pass
    else:
        err_log.append('子程序执行出错，请联系管理员')
    if len(err_log) > 0:
        print(err_log)
        c.write_log(log_list=err_log, log_file=log_file)
        sys.exit(1)
    else:
        c.del_all(os.path.dirname(log_file))
        c.del_all(os.path.join(outDir, 'tmp/analysis'), self_contain=True)
        c.del_all(os.path.join(outDir, 'tmp/tmp_data'), self_contain=True)
        print('此次任务顺利运行结束！\n')


if __name__ == "__main__":
    print(f"Start_time : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")
    par = basic_options()
    main(par)
    print(f"End_time : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")
