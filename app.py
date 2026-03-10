# -*- coding: utf-8 -*-
from nicegui import ui, app
from starlette.requests import Request
from starlette.responses import JSONResponse
import sqlite3
import pandas as pd
from datetime import datetime
import os
import tempfile
import webbrowser
import threading

DB_NAME = 'data.db'


def get_conn():
    #print("当前数据库路径:", os.path.abspath("data.db"))
    return sqlite3.connect("data.db")


conn = get_conn()
cursor = conn.cursor()

# =========================
# 创建多个表来记录流程
# =========================
# 表1: 法律初次上传数据
cursor.execute("""
CREATE TABLE IF NOT EXISTS stage1_law_upload (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    文号 TEXT NOT NULL,
    员工号 TEXT NOT NULL,
    被处理人 TEXT,
    所在机构 TEXT,
    处分文件名称 TEXT,
    问责发文时间 TEXT,
    税前金额 REAL,
    税后金额 REAL,
    纪律处分 TEXT,
    上传时间 TEXT,
    UNIQUE(文号, 员工号)
)
""")

# 表2: 人力反馈数据 - 包含表1的所有字段 + 新增字段
cursor.execute("""
CREATE TABLE IF NOT EXISTS stage2_hr_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    文号 TEXT NOT NULL,
    员工号 TEXT NOT NULL,
    被处理人 TEXT,
    所在机构 TEXT,
    处分文件名称 TEXT,
    问责发文时间 TEXT,
    税前金额 REAL,
    税后金额 REAL,
    纪律处分 TEXT,
    核算金额 REAL,
    备注 TEXT,
    反馈时间 TEXT,
    UNIQUE(文号, 员工号)
)
""")

# 表3: 法律最终修改数据 - 包含所有字段
cursor.execute("""
CREATE TABLE IF NOT EXISTS stage3_law_final (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    文号 TEXT NOT NULL,
    员工号 TEXT NOT NULL,
    被处理人 TEXT,
    所在机构 TEXT,
    处分文件名称 TEXT,
    问责发文时间 TEXT,
    税前金额 REAL,
    税后金额 REAL,
    纪律处分 TEXT,
    核算金额 REAL,
    备注 TEXT,
    最终修改时间 TEXT,
    UNIQUE(文号, 员工号)
)
""")

# 表4: 完整的案例数据（实时视图）
cursor.execute("""
CREATE TABLE IF NOT EXISTS case_data_view (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    文号 TEXT NOT NULL,
    员工号 TEXT NOT NULL,
    被处理人 TEXT,
    所在机构 TEXT,
    处分文件名称 TEXT,
    问责发文时间 TEXT,
    税前金额 REAL,
    税后金额 REAL,
    纪律处分 TEXT,
    核算金额 REAL,
    备注 TEXT,
    状态 TEXT,
    更新时间 TEXT,
    UNIQUE(文号, 员工号)
)
""")

# =========================
# 创建新表 - 问责办台账 (最终汇总表)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS accountability_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    文号 TEXT NOT NULL,
    员工号 TEXT NOT NULL,
    被处理人姓名 TEXT,
    分行 TEXT,
    政治面貌 TEXT,
    原所在机构 TEXT,
    原岗位类别 TEXT,
    原岗位职务 TEXT,
    现所在机构 TEXT,
    现岗位类别 TEXT,
    现岗位职务 TEXT,
    员工状态 TEXT,
    违规事实来源 TEXT,
    违规事实归属 TEXT,
    违规事实概述 TEXT,
    违规事实发现时间 TEXT,
    问责项目名称 TEXT,
    问责权限 TEXT,
    问责决策机构 TEXT,
    问责下达时间 TEXT,
    处理依据 TEXT,
    纪律处分类型 TEXT,
    经济处理金额 REAL,
    税后金额 REAL,
    合计经济处理金额 REAL,
    主要缴纳金额税前 REAL,
    主要缴纳金额税后 REAL,
    扣减当期绩效 REAL,
    扣减风险金 REAL,
    税后问责 REAL,
    税前执行金额 REAL,
    税前待执行剩余 REAL,
    税后执行金额 REAL,
    税后待执行剩余 REAL,
    合计执行金额 REAL,
    未执行到位金额 REAL,
    执行日期 TEXT,
    累计执行绩效金额 REAL,
    累计执行风险金金额 REAL,
    批评教育 TEXT,
    备注说明 TEXT,
    会议 TEXT,
    创建时间 TEXT,
    更新时间 TEXT,
    UNIQUE(文号, 员工号,执行日期)
)
""")

conn.commit()
conn.close()




# =========================
# API 路由 - 法律初次上传 (Stage 1)
# =========================
async def upload_law_file_stage1(request: Request):
    """处理法律初次上传 (Sheet1)"""
    try:
        form = await request.form()
        file = form.get('file')

        if not file:
            return JSONResponse({'success': False, 'message': '没有选择文件'})

        content = await file.read()
        if not content:
            return JSONResponse({'success': False, 'message': '文件为空'})

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f'law_stage1_{datetime.now().timestamp()}.xlsx')

        with open(temp_path, 'wb') as f:
            f.write(content)

        try:
            df = pd.read_excel(temp_path, sheet_name=0, header=1, dtype={'文号': str, '员工号': str})
            print(f"📊 法律初次上传 - 读取的列名: {list(df.columns)}")
            print(f"📊 数据行数: {len(df)}")
        except Exception as e:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': f'读取文件失败: {str(e)}'})

        if df.empty:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': '文件中没有数据'})

        inserted = 0
        conn = get_conn()
        cursor = conn.cursor()

        for idx, row in df.iterrows():
            try:
                wen_hao = str(row.get('文号', '')).strip() if pd.notna(row.get('文号')) else ''
                yuan_gong_hao = str(row.get('员工号', '')).strip() if pd.notna(row.get('员工号')) else ''

                if not wen_hao or not yuan_gong_hao:
                    print(f"⏭️ 行 {idx + 3} 跳过: 文号或员工号为空")
                    continue

                bei_chu_li_ren = str(row.get('被处理人', '')).strip() if pd.notna(row.get('被处理人')) else ''
                suo_zai_ji_gou = str(row.get('所在机构', '')).strip() if pd.notna(row.get('所在机构')) else ''
                chu_fen_wen_jian = str(row.get('处分文件名称', '')).strip() if pd.notna(row.get('处分文件名称')) else ''
                wen_ze_fa_wen_shi_jian = str(row.get('问责发文时间', '')).strip() if pd.notna(
                    row.get('问责发文时间')) else ''

                try:
                    shui_qian_jin_e = float(row.get('经济处理金额（税前）', 0)) if pd.notna(
                        row.get('经济处理金额（税前）')) else 0
                except:
                    shui_qian_jin_e = 0

                try:
                    shui_hou_jin_e = float(row.get('经济处理金额（税后）', 0)) if pd.notna(
                        row.get('经济处理金额（税后）')) else 0
                except:
                    shui_hou_jin_e = 0

                ji_lv_chu_fen = str(row.get('纪律处分', '')).strip() if pd.notna(row.get('纪律处分')) else ''

                # 插入到 stage1 表（包含员工号）
                cursor.execute("""
                    INSERT OR REPLACE INTO stage1_law_upload
                    (文号, 员工号, 被处理人, 所在机构, 处分文件名称, 问责发文时间,
                     税前金额, 税后金额, 纪律处分, 上传时间)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    wen_hao, yuan_gong_hao, bei_chu_li_ren, suo_zai_ji_gou, chu_fen_wen_jian, wen_ze_fa_wen_shi_jian,
                    shui_qian_jin_e, shui_hou_jin_e, ji_lv_chu_fen, datetime.now()
                ))

                # 同时更新 case_data_view 表（状态为 待人力反馈）
                cursor.execute("""
                    INSERT OR REPLACE INTO case_data_view
                    (文号, 员工号, 被处理人, 所在机构, 处分文件名称, 问责发文时间,
                     税前金额, 税后金额, 纪律处分, 状态, 更新时间)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    wen_hao, yuan_gong_hao, bei_chu_li_ren, suo_zai_ji_gou, chu_fen_wen_jian, wen_ze_fa_wen_shi_jian,
                    shui_qian_jin_e, shui_hou_jin_e, ji_lv_chu_fen, '待人力反馈', datetime.now()
                ))

                inserted += 1
                print(f"✅ 行 {idx + 3} 导入: 文号={wen_hao}, 员工号={yuan_gong_hao}")

            except Exception as e:
                print(f"❌ 行 {idx + 3} 导入失败: {e}")
                continue

        conn.commit()
        conn.close()
        os.remove(temp_path)

        return JSONResponse({
            'success': True,
            'message': f'✅ 法律初次上传成功！插入 {inserted} 条记录',
            'count': inserted
        })

    except Exception as e:
        print(f"法律初次上传错误: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({'success': False, 'message': f'服务器错误: {str(e)}'})


# =========================
# API 路由 - 人力反馈上传 (Stage 2)
# =========================
async def upload_hr_file_stage2(request: Request):
    """处理人力反馈上传 (Sheet2) - 包含 Stage1 的所有数据"""
    try:
        form = await request.form()
        file = form.get('file')

        if not file:
            return JSONResponse({'success': False, 'message': '没有选择文件'})

        content = await file.read()
        if not content:
            return JSONResponse({'success': False, 'message': '文件为空'})

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f'hr_stage2_{datetime.now().timestamp()}.xlsx')

        with open(temp_path, 'wb') as f:
            f.write(content)

        try:
            df = pd.read_excel(temp_path, sheet_name=0, dtype={'文号': str, '员工号': str})
            print(f"📊 人力反馈上传 - 读取的列名: {list(df.columns)}")
        except Exception as e:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': f'读取文件失败: {str(e)}'})

        if df.empty:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': '文件中没有数据'})

        updated = 0
        conn = get_conn()
        cursor = conn.cursor()

        for idx, row in df.iterrows():
            try:
                wen_hao = str(row.get('文号', '')).strip() if pd.notna(row.get('文号')) else ''
                yuan_gong_hao = str(row.get('员工号', '')).strip() if pd.notna(row.get('员工号')) else ''

                if not wen_hao or not yuan_gong_hao:
                    continue

                he_suan_jin_e = row.get('核算金额')
                bei_zhu = row.get('备注', '')

                # 从 case_data_view 获取完整的 stage1 数据
                cursor.execute("""
                    SELECT 被处理人, 所在机构, 处分文件名称, 问责发文时间,
                           税前金额, 税后金额, 纪律处分
                    FROM case_data_view WHERE 文号=? AND 员工号=?
                """, (wen_hao, yuan_gong_hao))

                stage1_data = cursor.fetchone()

                if stage1_data:
                    bei_chu_li_ren, suo_zai_ji_gou, chu_fen_wen_jian, wen_ze_fa_wen_shi_jian, shui_qian_jin_e, shui_hou_jin_e, ji_lv_chu_fen = stage1_data

                    # 保存到 stage2 表（包含 stage1 的所有数据 + 人力新增数据）
                    cursor.execute("""
                        INSERT OR REPLACE INTO stage2_hr_feedback
                        (文号, 员工号, 被处理人, 所在机构, 处分文件名称, 问责发文时间,
                         税前金额, 税后金额, 纪律处分, 核算金额, 备注, 反馈时间)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        wen_hao, yuan_gong_hao, bei_chu_li_ren, suo_zai_ji_gou, chu_fen_wen_jian,
                        wen_ze_fa_wen_shi_jian,
                        shui_qian_jin_e, shui_hou_jin_e, ji_lv_chu_fen, he_suan_jin_e, bei_zhu, datetime.now()
                    ))

                    # 更新 case_data_view 表
                    cursor.execute("""
                        UPDATE case_data_view
                        SET 核算金额=?, 备注=?, 状态=?, 更新时间=?
                        WHERE 文号=? AND 员工号=?
                    """, (
                        he_suan_jin_e, bei_zhu, '人力已反馈', datetime.now(), wen_hao, yuan_gong_hao
                    ))

                    updated += 1
                    print(f"✅ 人力反馈更新: 文号={wen_hao}, 员工号={yuan_gong_hao}")
                else:
                    print(f"⚠️ 文号 {wen_hao}, 员工号 {yuan_gong_hao} 在 stage1 中不存在")

            except Exception as e:
                print(f"❌ 行 {idx} 更新失败: {e}")
                continue

        conn.commit()
        conn.close()
        os.remove(temp_path)

        return JSONResponse({
            'success': True,
            'message': f'✅ 人力反馈上传成功！更新 {updated} 条记录',
            'count': updated
        })

    except Exception as e:
        print(f"人力反馈上传错误: {e}")
        return JSONResponse({'success': False, 'message': f'服务器错误: {str(e)}'})


# =========================
# API 路由 - 法律最终修改上传 (Stage 3)
# =========================
async def upload_law_file_stage3(request: Request):
    """处理法律最终修改上传 (Sheet1 - 第二次) - 根据人力核算金额修改税前和税后金额"""
    try:
        form = await request.form()
        file = form.get('file')

        if not file:
            return JSONResponse({'success': False, 'message': '没有选择文件'})

        content = await file.read()
        if not content:
            return JSONResponse({'success': False, 'message': '文件为空'})

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f'law_stage3_{datetime.now().timestamp()}.xlsx')

        with open(temp_path, 'wb') as f:
            f.write(content)

        try:
            # 关键修改：添加 header=0，表示第一行是列名（不跳过任何行）
            df = pd.read_excel(temp_path, sheet_name=0, header=0, dtype={'文号': str, '员工号': str})
            print(f"📊 法律最终修改 - 读取的列名: {list(df.columns)}")
            print(f"📊 读取行数: {len(df)}")
        except Exception as e:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': f'读取文件失败: {str(e)}'})

        if df.empty:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': '文件中没有数据'})

        updated = 0
        skipped = 0
        conn = get_conn()
        cursor = conn.cursor()

        for idx, row in df.iterrows():
            try:
                wen_hao = str(row.get('文号', '')).strip() if pd.notna(row.get('文号')) else ''
                yuan_gong_hao = str(row.get('员工号', '')).strip() if pd.notna(row.get('员工号')) else ''

                if not wen_hao or not yuan_gong_hao:
                    print(f"⏭️ 行 {idx + 2} 跳过: 文号或员工号为空")
                    skipped += 1
                    continue

                # 步骤1: 从 case_data_view 获取该文号+员工号的所有信息
                cursor.execute("""
                    SELECT 被处理人, 所在机构, 处分文件名称, 问责发文时间,
                           税前金额, 税后金额, 纪律处分, 核算金额, 备注
                    FROM case_data_view WHERE 文号=? AND 员工号=?
                """, (wen_hao, yuan_gong_hao))

                existing_data = cursor.fetchone()

                if not existing_data:
                    print(f"⚠️ 行 {idx + 2} 跳过: 文号 {wen_hao}, 员工号 {yuan_gong_hao} 在系统中不存在")
                    skipped += 1
                    continue

                # 获取现有数据
                (bei_chu_li_ren, suo_zai_ji_gou, chu_fen_wen_jian, wen_ze_fa_wen_shi_jian,
                 old_shui_qian_jin_e, old_shui_hou_jin_e, ji_lv_chu_fen, he_suan_jin_e, bei_zhu) = existing_data

                # 步骤2: 获取上传文件中的修改后的税前和税后金额
                try:
                    shui_qian_jin_e_new = float(row.get('经济处理金额（税前）')) if pd.notna(
                        row.get('经济处理金额（税前）')) else old_shui_qian_jin_e
                except:
                    shui_qian_jin_e_new = old_shui_qian_jin_e

                try:
                    shui_hou_jin_e_new = float(row.get('经济处理金额（税后）')) if pd.notna(
                        row.get('经济处理金额（税后）')) else old_shui_hou_jin_e
                except:
                    shui_hou_jin_e_new = old_shui_hou_jin_e

                # 其他字段保持不变
                bei_chu_li_ren_new = str(row.get('被处理人', '')).strip() if pd.notna(
                    row.get('被处理人')) else bei_chu_li_ren
                suo_zai_ji_gou_new = str(row.get('所在机构', '')).strip() if pd.notna(
                    row.get('所在机构')) else suo_zai_ji_gou
                chu_fen_wen_jian_new = str(row.get('处分文件名称', '')).strip() if pd.notna(
                    row.get('处分文件名称')) else chu_fen_wen_jian
                wen_ze_fa_wen_shi_jian_new = str(row.get('问责发文时间', '')).strip() if pd.notna(
                    row.get('问责发文时间')) else wen_ze_fa_wen_shi_jian
                ji_lv_chu_fen_new = str(row.get('纪律处分', '')).strip() if pd.notna(
                    row.get('纪律处分')) else ji_lv_chu_fen

                # 步骤3: 保存到 stage3 表（完整的最终数据）
                cursor.execute("""
                    INSERT OR REPLACE INTO stage3_law_final
                    (文号, 员工号, 被处理人, 所在机构, 处分文件名称, 问责发文时间,
                     税前金额, 税后金额, 纪律处分, 核算金额, 备注, 最终修改时间)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    wen_hao, yuan_gong_hao, bei_chu_li_ren_new, suo_zai_ji_gou_new, chu_fen_wen_jian_new,
                    wen_ze_fa_wen_shi_jian_new,
                    shui_qian_jin_e_new, shui_hou_jin_e_new, ji_lv_chu_fen_new, he_suan_jin_e, bei_zhu, datetime.now()
                ))

                # 步骤4: 同时更新 case_data_view 表（最终状态）
                cursor.execute("""
                    UPDATE case_data_view
                    SET 被处理人=?, 所在机构=?, 处分文件名称=?, 问责发文时间=?,
                        税前金额=?, 税后金额=?, 纪律处分=?, 状态=?, 更新时间=?
                    WHERE 文号=? AND 员工号=?
                """, (
                    bei_chu_li_ren_new, suo_zai_ji_gou_new, chu_fen_wen_jian_new, wen_ze_fa_wen_shi_jian_new,
                    shui_qian_jin_e_new, shui_hou_jin_e_new, ji_lv_chu_fen_new, '已完成', datetime.now(), wen_hao,
                    yuan_gong_hao
                ))

                updated += 1
                print(f"✅ 行 {idx + 2} 更新成功: 文号={wen_hao}, 员工号={yuan_gong_hao}")
                print(f"   核算金额(人力): {he_suan_jin_e}")
                print(f"   税前金额: {old_shui_qian_jin_e} → {shui_qian_jin_e_new}")
                print(f"   税后金额: {old_shui_hou_jin_e} → {shui_hou_jin_e_new}")

            except Exception as e:
                print(f"❌ 行 {idx + 2} 更新失败: {e}")
                import traceback
                traceback.print_exc()
                skipped += 1
                continue

        conn.commit()
        conn.close()
        os.remove(temp_path)

        message = f'✅ 法律最终修改成功！更新 {updated} 条记录'
        if skipped > 0:
            message += f'，跳过 {skipped} 条'

        return JSONResponse({
            'success': True,
            'message': message,
            'count': updated
        })

    except Exception as e:
        print(f"法律最终修改错误: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({'success': False, 'message': f'服务器错误: {str(e)}'})


# =========================
# API 路由 - 问责办台账上传
# =========================
async def upload_accountability_ledger(request: Request):
    """处理问责办台账上传 - 手工录入后自动计算派生字段"""
    try:
        form = await request.form()
        file = form.get('file')

        if not file:
            return JSONResponse({'success': False, 'message': '没有选择文件'})

        content = await file.read()
        if not content:
            return JSONResponse({'success': False, 'message': '文件为空'})

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f'ledger_{datetime.now().timestamp()}.xlsx')

        with open(temp_path, 'wb') as f:
            f.write(content)

        try:
            df = pd.read_excel(temp_path, sheet_name=0, dtype={'文号': str, '员工号': str,
        '执行日期': str})
            print(f"📊 问责办台账上传 - 读取的列名: {list(df.columns)}")
            print(f"📊 读取行数: {len(df)}")
        except Exception as e:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': f'读取文件失败: {str(e)}'})

        if df.empty:
            os.remove(temp_path)
            return JSONResponse({'success': False, 'message': '文件中没有数据'})


        # =========================
        # 日期处理 + 排序
        # =========================
        df["执行日期"] = (
            df["执行日期"]
            .astype(str)
            .str.replace("-", "")
            .str.replace("/", "")
            .str[:6]
        )

        df = df.sort_values(["文号","员工号", "执行日期"])

        inserted = 0
        conn = get_conn()
        cursor = conn.cursor()
        for idx, row in df.iterrows():
            try:
                wen_hao = str(row.get('文号', '')).strip() if pd.notna(row.get('文号')) else ''
                yuan_gong_id = str(row.get('员工号', '')).strip() if pd.notna(row.get('员工号')) else ''

                if not wen_hao or not yuan_gong_id:
                    print(f"⏭️ 行 {idx + 2} 跳过: 文号或员工号为空")
                    continue

                # 获取手工录入的字段
                fen_xing = str(row.get('分行', '')).strip() if pd.notna(row.get('分行')) else ''
                bei_chu_li_ren = str(row.get('被处理人姓名', '')).strip() if pd.notna(row.get('被处理人姓名')) else ''
                zheng_zhi_mian_mao = str(row.get('政治面貌', '')).strip() if pd.notna(row.get('政治面貌')) else ''
                yuan_suo_zai_ji_gou = str(row.get('原所在机构（部门）', '')).strip() if pd.notna(
                    row.get('原所在机构（部门）')) else ''
                yuan_gang_wei_lei_bie = str(row.get('原岗位类别', '')).strip() if pd.notna(
                    row.get('原岗位类别')) else ''
                yuan_gang_wei_zhi_wu = str(row.get('原岗位职务', '')).strip() if pd.notna(row.get('原岗位职务')) else ''
                xian_suo_zai_ji_gou = str(row.get('现所在机构（部门）', '')).strip() if pd.notna(
                    row.get('现所在机构（部门）')) else ''
                xian_gang_wei_lei_bie = str(row.get('现岗位类别', '')).strip() if pd.notna(
                    row.get('现岗位类别')) else ''
                xian_gang_wei_zhi_wu = str(row.get('现岗位职务', '')).strip() if pd.notna(row.get('现岗位职务')) else ''
                yuan_gong_zhuang_tai = str(row.get('员工状态', '')).strip() if pd.notna(row.get('员工状态')) else ''
                wei_gui_shi_shi_lai_yuan = str(row.get('违规事实来源', '')).strip() if pd.notna(
                    row.get('违规事实来源')) else ''
                wei_gui_shi_shi_gui_shu = str(row.get('违规事实归属', '')).strip() if pd.notna(
                    row.get('违规事实归属')) else ''
                wei_gui_shi_shi_gai_shu = str(row.get('违规事实概述', '')).strip() if pd.notna(
                    row.get('违规事实概述')) else ''
                wei_gui_shi_shi_fa_xian_shi_jian = str(row.get('违规事实发现时间', '')).strip() if pd.notna(
                    row.get('违规事实发现时间')) else ''
                wen_ze_xiang_mu_ming = str(row.get('问责项目名称', '')).strip() if pd.notna(
                    row.get('问责项目名称')) else ''
                wen_ze_quan_xian = str(row.get('问责权限', '')).strip() if pd.notna(row.get('问责权限')) else ''
                wen_ze_jue_ce_ji_gou = str(row.get('问责决策机构', '')).strip() if pd.notna(
                    row.get('问责决策机构')) else ''
                wen_ze_xia_da_shi_jian = str(row.get('问责下达时间', '')).strip() if pd.notna(
                    row.get('问责下达时间')) else ''
                chu_li_yi_ju = str(row.get('处理依据', '')).strip() if pd.notna(row.get('处理依据')) else ''
                ji_lv_chu_fen_lei_xing = str(row.get('纪律处分类型', '')).strip() if pd.notna(
                    row.get('纪律处分类型')) else ''

                # 获取数值字段
                try:
                    jing_ji_chu_li = float(row.get('经济处理金额（元）', 0)) if pd.notna(
                        row.get('经济处理金额（元）')) else 0
                except:
                    jing_ji_chu_li = 0

                try:
                    shui_hou = float(row.get('税后（元）', 0)) if pd.notna(row.get('税后（元）')) else 0
                except:
                    shui_hou = 0

                try:
                    he_ji_jing_ji = float(row.get('合计经济处理金额（元）', 0)) if pd.notna(
                        row.get('合计经济处理金额（元）')) else 0
                except:
                    he_ji_jing_ji = 0

                try:
                    zhu_yao_jiao_na_shui_qian = float(row.get('主要缴纳金额(税前）', 0)) if pd.notna(
                        row.get('主要缴纳金额(税前）')) else 0
                except:
                    zhu_yao_jiao_na_shui_qian = 0

                try:
                    zhu_yao_jiao_na_shui_hou = float(row.get('主要缴纳金额(税后）', 0)) if pd.notna(
                        row.get('主要缴纳金额(税后）')) else 0
                except:
                    zhu_yao_jiao_na_shui_hou = 0

                try:
                    kou_jian_ji_xiao = float(row.get('扣减当期绩效', 0)) if pd.notna(row.get('扣减当期绩效', 0)) else 0
                except:
                    kou_jian_ji_xiao = 0

                try:
                    kou_jian_feng_xian = float(row.get('扣减风险金', 0)) if pd.notna(row.get('扣减风险金', 0)) else 0
                except:
                    kou_jian_feng_xian = 0

                try:
                    shui_hou_wen_ze = float(row.get('税后问责', 0)) if pd.notna(row.get('税后问责', 0)) else 0
                except:
                    shui_hou_wen_ze = 0

                value = row.get('执行日期')

                if pd.isna(value):
                    zhi_xing_ri_qi = ''
                else:
                    if isinstance(value, (pd.Timestamp, datetime)):
                        zhi_xing_ri_qi = value.strftime("%Y%m")
                    else:
                        zhi_xing_ri_qi = str(value).replace("-", "").replace("/", "")[:6]

                try:
                    lei_ji_zhi_xing_ji_xiao = float(row.get('累计执行绩效金额', 0)) if pd.notna(
                        row.get('累计执行绩效金额', 0)) else 0
                except:
                    lei_ji_zhi_xing_ji_xiao = 0

                try:
                    lei_ji_zhi_xing_feng_xian = float(row.get('累计执行风险金金额', 0)) if pd.notna(
                        row.get('累计执行风险金金额', 0)) else 0
                except:
                    lei_ji_zhi_xing_feng_xian = 0

                pi_ping_jiao_yu = str(row.get('批评教育', '')).strip() if pd.notna(row.get('批评教育')) else ''
                bei_zhu = str(row.get('备注说明', '')).strip() if pd.notna(row.get('备注说明')) else ''
                hui_yi = str(row.get('会议', '')).strip() if pd.notna(row.get('会议')) else ''

                # ========== 自动计算派生字段 ==========
                # 税前执行金额 = 主要缴纳金额(税前）+ 扣减当期绩效 + 扣减风险金
                shui_qian_zhi_xing = zhu_yao_jiao_na_shui_qian + kou_jian_ji_xiao + kou_jian_feng_xian

                # 税前待执行金额剩余 = 经济处理金额（元）- 税前执行金额
                shui_qian_dai_zhi_xing = jing_ji_chu_li - shui_qian_zhi_xing

                # 税后执行金额 = 主要缴纳金额(税后）+ 税后问责
                shui_hou_zhi_xing = zhu_yao_jiao_na_shui_hou + shui_hou_wen_ze

                # 税后待执行剩余金额 = 税后（元）- 税后执行金额
                shui_hou_dai_zhi_xing = shui_hou - shui_hou_zhi_xing

                # 合计执行金额 = 税前执行金额 + 税后执行金额
                he_ji_zhi_xing = shui_qian_zhi_xing + shui_hou_zhi_xing

                # 未执行到位金额 = 合计经济处理金额（元）- 合计执行金额
                wei_zhi_xing = he_ji_jing_ji - he_ji_zhi_xing

                # 保存到数据库
                cursor.execute("""
                SELECT 累计执行绩效金额, 累计执行风险金金额
                FROM accountability_ledger
                WHERE 文号=? AND 员工号=? AND 执行日期 < ?
                ORDER BY 执行日期 DESC
                LIMIT 1
                """, (wen_hao, yuan_gong_id, zhi_xing_ri_qi))

                last = cursor.fetchone()

                if last:
                    last_perf = last[0] or 0
                    last_risk = last[1] or 0
                else:
                    last_perf = 0
                    last_risk = 0

                # 当前累计
                kou_jian_ji_xiao = float(kou_jian_ji_xiao or 0)
                kou_jian_feng_xian = float(kou_jian_feng_xian or 0)

                lei_ji_zhi_xing_ji_xiao = last_perf + kou_jian_ji_xiao
                lei_ji_zhi_xing_feng_xian = last_risk + kou_jian_feng_xian


                cursor.execute("""
                    INSERT OR REPLACE INTO accountability_ledger
                    (员工号, 被处理人姓名, 分行, 政治面貌, 原所在机构, 原岗位类别, 原岗位职务,
                     现所在机构, 现岗位类别, 现岗位职务, 员工状态, 违规事实来源, 违规事实归属, 违规事实概述,
                     违规事实发现时间, 问责项目名称, 文号, 问责权限, 问责决策机构, 问责下达时间,
                     处理依据, 纪律处分类型, 经济处理金额, 税后金额, 合计经济处理金额,
                     主要缴纳金额税前, 主要缴纳金额税后, 扣减当期绩效, 扣减风险金, 税后问责,
                     税前执行金额, 税前待执行剩余, 税后执行金额, 税后待执行剩余, 合计执行金额,
                     未执行到位金额, 执行日期, 累计执行绩效金额, 累计执行风险金金额, 批评教育,
                     备注说明, 会议, 创建时间, 更新时间)
                    VALUES ( ?,?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                     yuan_gong_id, bei_chu_li_ren, fen_xing, zheng_zhi_mian_mao,
                    yuan_suo_zai_ji_gou, yuan_gang_wei_lei_bie, yuan_gang_wei_zhi_wu,
                    xian_suo_zai_ji_gou, xian_gang_wei_lei_bie, xian_gang_wei_zhi_wu,
                    yuan_gong_zhuang_tai, wei_gui_shi_shi_lai_yuan, wei_gui_shi_shi_gui_shu, wei_gui_shi_shi_gai_shu,
                    wei_gui_shi_shi_fa_xian_shi_jian, wen_ze_xiang_mu_ming, wen_hao, wen_ze_quan_xian,
                    wen_ze_jue_ce_ji_gou,
                    wen_ze_xia_da_shi_jian, chu_li_yi_ju, ji_lv_chu_fen_lei_xing,
                    jing_ji_chu_li, shui_hou, he_ji_jing_ji,
                    zhu_yao_jiao_na_shui_qian, zhu_yao_jiao_na_shui_hou, kou_jian_ji_xiao, kou_jian_feng_xian,
                    shui_hou_wen_ze,
                    shui_qian_zhi_xing, shui_qian_dai_zhi_xing, shui_hou_zhi_xing, shui_hou_dai_zhi_xing,
                    he_ji_zhi_xing,
                    wei_zhi_xing, zhi_xing_ri_qi, lei_ji_zhi_xing_ji_xiao, lei_ji_zhi_xing_feng_xian, pi_ping_jiao_yu,
                    bei_zhu, hui_yi, datetime.now(), datetime.now()
                ))

                inserted += 1
                print(f"✅ 行 {idx + 2} 导入: 文号={wen_hao}, 员工号={yuan_gong_id}")
                print(f"   自动计算:")
                print(f"   - 税前执行金额: {shui_qian_zhi_xing}")
                print(f"   - 税前待执行剩余: {shui_qian_dai_zhi_xing}")
                print(f"   - 税后执行金额: {shui_hou_zhi_xing}")
                print(f"   - 税后待执行剩余: {shui_hou_dai_zhi_xing}")
                print(f"   - 合计执行金额: {he_ji_zhi_xing}")
                print(f"   - 未执行到位金额: {wei_zhi_xing}")

            except Exception as e:
                print(f"❌ 行 {idx + 2} 导入失败: {e}")
                import traceback
                traceback.print_exc()
                continue

        conn.commit()
        conn.close()
        os.remove(temp_path)

        return JSONResponse({
            'success': True,
            'message': f'✅ 问责办台账上传成功！插入 {inserted} 条记录（派生字段已自动计算）',
            'count': inserted
        })

    except Exception as e:
        print(f"问责办台账上传错误: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({'success': False, 'message': f'服务器错误: {str(e)}'})




# =========================
# 注册 API 路由
# =========================
@app.post('/upload_law_stage1')
async def handle_upload_law_stage1(request: Request):
    return await upload_law_file_stage1(request)


@app.post('/upload_hr_stage2')
async def handle_upload_hr_stage2(request: Request):
    return await upload_hr_file_stage2(request)


@app.post('/upload_law_stage3')
async def handle_upload_law_stage3(request: Request):
    return await upload_law_file_stage3(request)

@app.post('/upload_accountability_ledger')
async def handle_upload_accountability_ledger(request: Request):
    return await upload_accountability_ledger(request)
# =========================
# 页面1 法律初次上传 (Stage 1)
# =========================
@ui.page('/')
def law_upload_stage1():
    ui.label('⏹️ Stage 1: 法律初次上传 sheet1').classes('text-h4').style('color: #FF6B6B')

    upload_html = '''
    <div style="margin: 20px 0; padding: 20px; border: 3px dashed #FF6B6B; border-radius: 8px; background-color: #ffe8e8;">
        <input type="file" id="lawFile1" accept=".xlsx,.xls" style="display: none;">
        <button id="lawChooseBtn1" style="margin-bottom: 10px; padding: 12px 20px; background-color: #FF9800; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold;">
            📁 选择 Excel 文件
        </button>
        <button id="lawUploadBtn1" style="padding: 12px 20px; background-color: #FF6B6B; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold;">
            📤 上传法律初始数据
        </button>
        <div id="lawFileName1" style="margin-top: 10px; color: #FF6B6B; font-size: 14px; text-align: center; font-weight: bold;"></div>
        <div id="lawStatus1" style="margin-top: 10px; color: #666; font-size: 14px; text-align: center;"></div>
    </div>
    '''

    ui.html(upload_html)

    js_code = '''
    const fileInput1 = document.getElementById('lawFile1');
    const chooseBtn1 = document.getElementById('lawChooseBtn1');
    const uploadBtn1 = document.getElementById('lawUploadBtn1');
    const fileName1 = document.getElementById('lawFileName1');
    const status1 = document.getElementById('lawStatus1');

    chooseBtn1.addEventListener('click', function() {
        fileInput1.click();
    });

    fileInput1.addEventListener('change', function() {
        if (this.files[0]) {
            fileName1.textContent = '✅ 已选择: ' + this.files[0].name;
            fileName1.style.color = '#FF6B6B';
        }
    });

    uploadBtn1.addEventListener('click', async function() {
        const file = fileInput1.files[0];

        if (!file) {
            status1.textContent = '❌ 请先选择文件！';
            status1.style.color = 'red';
            return;
        }

        status1.textContent = '📥 正在上传...';
        status1.style.color = '#666';
        uploadBtn1.disabled = true;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload_law_stage1', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                status1.textContent = '✅ ' + data.message;
                status1.style.color = 'green';
                fileName1.textContent = '';
                fileInput1.value = '';
                uploadBtn1.disabled = false;
                setTimeout(() => location.reload(), 2000);
            } else {
                status1.textContent = '❌ ' + data.message;
                status1.style.color = 'red';
                uploadBtn1.disabled = false;
            }
        } catch (error) {
            status1.textContent = '❌ 上传失败: ' + error.message;
            status1.style.color = 'red';
            uploadBtn1.disabled = false;
        }
    });
    '''

    ui.run_javascript(js_code)

    ui.separator()

    # 在页面1首页的导航链接中添加：
    with ui.row().classes('gap-4'):
        ui.link('👉 Stage 2: 人力下载模板', '/hr_download_stage2').classes('text-blue-600')
        ui.link('👉 Stage 2: 人力上传反馈', '/hr_upload_stage2').classes('text-blue-600')
        ui.link('👉 Stage 3: 法律下载结果', '/law_download_stage3').classes('text-blue-600')
        ui.link('👉 Stage 3: 法律再次上传', '/law_upload_stage3').classes('text-blue-600')
        ui.link('👉 问责办台账', '/accountability_ledger').classes('text-purple-600')  # 新增
        ui.link('👉 查看完整数据', '/view_all').classes('text-blue-600')


# =========================
# 页面2 人力下载模板 (Stage 2)
# =========================
@ui.page('/hr_download_stage2')
def hr_download_stage2():
    ui.label('⏹️ Stage 2: 人力下载模板').classes('text-h4').style('color: #4CAF50')

    def generate():
        try:
            conn = get_conn()
            df = pd.read_sql("SELECT * FROM case_data_view WHERE 状态='待人力反馈'", conn)
            conn.close()

            if df.empty:
                ui.notify('没有待处理数据', color='orange')
                return

            export = pd.DataFrame()
            export['序号'] = range(1, len(df)+1)
            export['员工号'] = df['员工号']
            export['被处理人'] = df['被处理人']
            export['所在机构'] = df['所在机构']
            export['文号'] = df['文号']
            export['处分文件名称'] = df['处分文件名称']
            export['问责发文时间'] = df['问责发文时间']
            export['经济处理金额（税前）'] = df['税前金额']
            export['核算金额'] = ''
            export['经济处理金额（税后）'] = df['税后金额']
            export['纪律处分'] = df['纪律处分']
            export['备注'] = ''

            file_name = '人力反馈模板.xlsx'
            export.to_excel(file_name, index=False)
            ui.download(file_name)
            ui.notify('✅ 模板下载成功', color='green')
        except Exception as e:
            ui.notify(f'❌ {str(e)}', color='red')

    ui.button('生成并下载模板', on_click=generate).classes('bg-green-500 text-white')
    ui.link('👉 返回', '/').classes('text-blue-600')


# =========================
# 页面3 人力上传反馈 (Stage 2)
# =========================
@ui.page('/hr_upload_stage2')
def hr_upload_stage2():
    ui.label('⏹️ Stage 2: 人力上传反馈 sheet2').classes('text-h4').style('color: #4CAF50')

    upload_html = '''
    <div style="margin: 20px 0; padding: 20px; border: 3px dashed #4CAF50; border-radius: 8px; background-color: #e8f5e9;">
        <input type="file" id="hrFile2" accept=".xlsx,.xls" style="display: none;">
        <button id="hrChooseBtn2" style="margin-bottom: 10px; padding: 12px 20px; background-color: #FF9800; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold;">
            📁 选择 Excel 文件
        </button>
        <button id="hrUploadBtn2" style="padding: 12px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold;">
            📤 上传人力反馈
        </button>
        <div id="hrFileName2" style="margin-top: 10px; color: #4CAF50; font-size: 14px; text-align: center; font-weight: bold;"></div>
        <div id="hrStatus2" style="margin-top: 10px; color: #666; font-size: 14px; text-align: center;"></div>
    </div>
    '''

    ui.html(upload_html)

    js_code = '''
    const hrFileInput2 = document.getElementById('hrFile2');
    const hrChooseBtn2 = document.getElementById('hrChooseBtn2');
    const hrUploadBtn2 = document.getElementById('hrUploadBtn2');
    const hrFileName2 = document.getElementById('hrFileName2');
    const hrStatus2 = document.getElementById('hrStatus2');

    hrChooseBtn2.addEventListener('click', function() {
        hrFileInput2.click();
    });

    hrFileInput2.addEventListener('change', function() {
        if (this.files[0]) {
            hrFileName2.textContent = '✅ 已选择: ' + this.files[0].name;
            hrFileName2.style.color = '#4CAF50';
        }
    });

    hrUploadBtn2.addEventListener('click', async function() {
        const file = hrFileInput2.files[0];

        if (!file) {
            hrStatus2.textContent = '❌ 请先选择文件！';
            hrStatus2.style.color = 'red';
            return;
        }

        hrStatus2.textContent = '📥 正在上传...';
        hrStatus2.style.color = '#666';
        hrUploadBtn2.disabled = true;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload_hr_stage2', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                hrStatus2.textContent = '✅ ' + data.message;
                hrStatus2.style.color = 'green';
                hrFileName2.textContent = '';
                hrFileInput2.value = '';
                hrUploadBtn2.disabled = false;
                setTimeout(() => location.reload(), 2000);
            } else {
                hrStatus2.textContent = '❌ ' + data.message;
                hrStatus2.style.color = 'red';
                hrUploadBtn2.disabled = false;
            }
        } catch (error) {
            hrStatus2.textContent = '❌ 上传失败: ' + error.message;
            hrStatus2.style.color = 'red';
            hrUploadBtn2.disabled = false;
        }
    });
    '''

    ui.run_javascript(js_code)

    ui.link('👉 返回', '/').classes('text-blue-600')


# =========================
# 页面4 法律下载结果 (Stage 3)
# =========================
@ui.page('/law_download_stage3')
def law_download_stage3():
    ui.label('⏹️ Stage 3: 法律下载反馈结果（修改税前/税后金额）').classes('text-h4').style('color: #2196F3')

    def download():
        try:
            conn = get_conn()
            # 获取"人力已反馈"状态的数据，这样包含了核算金额
            df = pd.read_sql("SELECT * FROM case_data_view WHERE 状态='人力已反馈'", conn)
            conn.close()

            if df.empty:
                ui.notify('暂无人力已反馈的数据', color='orange')
                return

            # 导出时保持和人力反馈模板相同的格式，便于法律修改后上传
            export = pd.DataFrame()
            export['序号'] = range(1, len(df)+1)
            export['员工号'] = df['员工号']
            export['被处理人'] = df['被处理人']
            export['所在机构'] = df['所在机构']
            export['文号'] = df['文号']
            export['处分文件名称'] = df['处分文件名称']
            export['问责发文时间'] = df['问责发文时间']
            export['经济处理金额（税前）'] = df['税前金额']  # 法律需要修改这个字段
            export['核算金额'] = df['核算金额']  # 人力反馈的核算金额（参考值）
            export['经济处理金额（税后）'] = df['税后金额']  # 法律需要修改这个字段
            export['纪律处分'] = df['纪律处分']
            export['备注'] = df['备注']

            file_name = '法律反馈结果.xlsx'
            export.to_excel(file_name, index=False)
            ui.download(file_name)
            ui.notify('✅ 法律反馈结果下载成功（请修改税前/税后金额后再上传）', color='green')
        except Exception as e:
            ui.notify(f'❌ {str(e)}', color='red')

    ui.button('下载反馈结果', on_click=download).classes('bg-blue-500 text-white')
    ui.link('👉 返回', '/').classes('text-blue-600')


# =========================
# 页面5 法律再次上传 (Stage 3)
# =========================
@ui.page('/law_upload_stage3')
def law_upload_stage3():
    ui.label('⏹️ Stage 3: 法律再次修改上传 sheet1').classes('text-h4').style('color: #2196F3')

    upload_html = '''
    <div style="margin: 20px 0; padding: 20px; border: 3px dashed #2196F3; border-radius: 8px; background-color: #e3f2fd;">
        <input type="file" id="lawFile3" accept=".xlsx,.xls" style="display: none;">
        <button id="lawChooseBtn3" style="margin-bottom: 10px; padding: 12px 20px; background-color: #FF9800; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold;">
            📁 选择 Excel 文件
        </button>
        <button id="lawUploadBtn3" style="padding: 12px 20px; background-color: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold;">
            📤 上传法律最终修改
        </button>
        <div id="lawFileName3" style="margin-top: 10px; color: #2196F3; font-size: 14px; text-align: center; font-weight: bold;"></div>
        <div id="lawStatus3" style="margin-top: 10px; color: #666; font-size: 14px; text-align: center;"></div>
    </div>
    '''

    ui.html(upload_html)

    js_code = '''
    const fileInput3 = document.getElementById('lawFile3');
    const chooseBtn3 = document.getElementById('lawChooseBtn3');
    const uploadBtn3 = document.getElementById('lawUploadBtn3');
    const fileName3 = document.getElementById('lawFileName3');
    const status3 = document.getElementById('lawStatus3');

    chooseBtn3.addEventListener('click', function() {
        fileInput3.click();
    });

    fileInput3.addEventListener('change', function() {
        if (this.files[0]) {
            fileName3.textContent = '✅ 已选择: ' + this.files[0].name;
            fileName3.style.color = '#2196F3';
        }
    });

    uploadBtn3.addEventListener('click', async function() {
        const file = fileInput3.files[0];

        if (!file) {
            status3.textContent = '❌ 请先选择文件！';
            status3.style.color = 'red';
            return;
        }

        status3.textContent = '📥 正在上传...';
        status3.style.color = '#666';
        uploadBtn3.disabled = true;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload_law_stage3', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                status3.textContent = '✅ ' + data.message;
                status3.style.color = 'green';
                fileName3.textContent = '';
                fileInput3.value = '';
                uploadBtn3.disabled = false;
                setTimeout(() => location.reload(), 2000);
            } else {
                status3.textContent = '❌ ' + data.message;
                status3.style.color = 'red';
                uploadBtn3.disabled = false;
            }
        } catch (error) {
            status3.textContent = '❌ 上传失败: ' + error.message;
            status3.style.color = 'red';
            uploadBtn3.disabled = false;
        }
    });
    '''

    ui.run_javascript(js_code)

    ui.link('👉 返回', '/').classes('text-blue-600')


# =========================
# 页面6 查看完整数据
# =========================
@ui.page('/view_all')
def view_all():
    ui.label('📊 完整数据视图').classes('text-h4')

    # 改为垂直排列的 tabs
    with ui.tabs().props('vertical') as tabs:
        with ui.tab('完整数据（实时视图）'):
            conn = get_conn()
            df = pd.read_sql("SELECT * FROM case_data_view ORDER BY 更新时间 DESC LIMIT 5", conn)
            conn.close()

            if not df.empty:
                ui.label(f'最近 5 条数据').classes('text-lg font-bold')
                ui.table.from_pandas(df).classes('w-full')

                # 添加下载按钮
                def download_view():
                    try:
                        conn = get_conn()
                        df = pd.read_sql("SELECT * FROM case_data_view ORDER BY 更新时间 DESC", conn)
                        conn.close()

                        if df.empty:
                            ui.notify('暂无数据', color='orange')
                            return

                        file_name = '完整数据视图.xlsx'
                        df.to_excel(file_name, index=False)
                        ui.download(file_name)
                        ui.notify('✅ 下载成功', color='green')
                    except Exception as e:
                        ui.notify(f'❌ 下载失败: {str(e)}', color='red')

                ui.button('📥 下载此表', on_click=download_view).classes('bg-blue-500 text-white')
            else:
                ui.label('暂无数据').classes('text-gray-500')

        with ui.tab('Stage 1: 法律初始数据'):
            conn = get_conn()
            df = pd.read_sql("SELECT * FROM stage1_law_upload ORDER BY 上传时间 DESC LIMIT 5", conn)
            conn.close()

            if not df.empty:
                ui.label(f'最近 5 条数据').classes('text-lg font-bold')
                ui.table.from_pandas(df).classes('w-full')

                # 添加下载按钮
                def download_stage1():
                    try:
                        conn = get_conn()
                        df = pd.read_sql("SELECT * FROM stage1_law_upload ORDER BY 上传时间 DESC", conn)
                        conn.close()

                        if df.empty:
                            ui.notify('暂无数据', color='orange')
                            return

                        file_name = 'Stage1_法律初始数据.xlsx'
                        df.to_excel(file_name, index=False)
                        ui.download(file_name)
                        ui.notify('✅ 下载成功', color='green')
                    except Exception as e:
                        ui.notify(f'❌ 下载失败: {str(e)}', color='red')

                ui.button('📥 下载此表', on_click=download_stage1).classes('bg-blue-500 text-white')
            else:
                ui.label('暂无数据').classes('text-gray-500')

        with ui.tab('Stage 2: 人力反馈'):
            conn = get_conn()
            df = pd.read_sql("SELECT * FROM stage2_hr_feedback ORDER BY 反馈时间 DESC LIMIT 5", conn)
            conn.close()

            if not df.empty:
                ui.label(f'最近 5 条数据').classes('text-lg font-bold')
                ui.table.from_pandas(df).classes('w-full')

                # 添加下载按钮
                def download_stage2():
                    try:
                        conn = get_conn()
                        df = pd.read_sql("SELECT * FROM stage2_hr_feedback ORDER BY 反馈时间 DESC", conn)
                        conn.close()

                        if df.empty:
                            ui.notify('暂无数据', color='orange')
                            return

                        file_name = 'Stage2_人力反馈.xlsx'
                        df.to_excel(file_name, index=False)
                        ui.download(file_name)
                        ui.notify('✅ 下载成功', color='green')
                    except Exception as e:
                        ui.notify(f'❌ 下载失败: {str(e)}', color='red')

                ui.button('📥 下载此表', on_click=download_stage2).classes('bg-blue-500 text-white')
            else:
                ui.label('暂无数据').classes('text-gray-500')

        with ui.tab('Stage 3: 法律最终'):
            conn = get_conn()
            df = pd.read_sql("SELECT * FROM stage3_law_final ORDER BY 最终修改时间 DESC LIMIT 5", conn)
            conn.close()

            if not df.empty:
                ui.label(f'最近 5 条数据').classes('text-lg font-bold')
                ui.table.from_pandas(df).classes('w-full')

                # 添加下载按钮
                def download_stage3():
                    try:
                        conn = get_conn()
                        df = pd.read_sql("SELECT * FROM stage3_law_final ORDER BY 最终修改时间 DESC", conn)
                        conn.close()

                        if df.empty:
                            ui.notify('暂无数据', color='orange')
                            return

                        file_name = 'Stage3_法律最终.xlsx'
                        df.to_excel(file_name, index=False)
                        ui.download(file_name)
                        ui.notify('✅ 下载成功', color='green')
                    except Exception as e:
                        ui.notify(f'❌ 下载失败: {str(e)}', color='red')

                ui.button('📥 下载此表', on_click=download_stage3).classes('bg-blue-500 text-white')
            else:
                ui.label('暂无数据').classes('text-gray-500')

    ui.separator()
    ui.link('👉 返回', '/').classes('text-blue-600')


# =========================
# 页面7 问责办台账管理
# =========================
@ui.page('/accountability_ledger')
def accountability_ledger_page():
    with ui.column().classes('w-full').style('max-width:1400px;margin:auto'):
        ui.label('📋 问责办台账管理').classes('text-h4').style('color: #9C27B0')

        # =========================
        # 页面左右布局 —— 重点修改：添加 gap、align-items、max-height 控制
        # =========================
        with ui.row().classes('w-full no-wrap gap-4').style('align-items: flex-start;'):

            # =========================
            # 左侧：Tab操作区（重点调整：给左侧列添加 padding 并限制按钮宽度 + 高度滚动）
            # =========================
            with ui.column().classes('w-1/3 p-4').style('max-height: 80vh; overflow-y: auto;'):  # 👈 限制高度，允许滚动
                with ui.tabs().props('vertical align=left'):

                    # =========================
                    # Tab 1: 下载空白模板
                    # =========================
                    with ui.tab('下载空白模板'):
                        with ui.column().classes('w-full gap-4'):

                            ui.label('下载空白台账模板进行填写').classes('text-md')

                            def download_template():
                                try:
                                    template = pd.DataFrame({
                                        '分行': [''],
                                        '员工号': [''],
                                        '被处理人姓名': [''],
                                        '政治面貌': [''],
                                        '原所在机构（部门）': [''],
                                        '原岗位类别': [''],
                                        '原岗位职务': [''],
                                        '现所在机构（部门）': [''],
                                        '现岗位类别': [''],
                                        '现岗位职务': [''],
                                        '员工状态': [''],
                                        '违规事实来源': [''],
                                        '违规事实归属': [''],
                                        '违规事实概述': [''],
                                        '违规事实发现时间': [''],
                                        '问责项目名称': [''],
                                        '文号': [''],
                                        '问责权限': [''],
                                        '问责决策机构': [''],
                                        '问责下达时间': [''],
                                        '处理依据': [''],
                                        '纪律处分类型': [''],
                                        '经济处理金额（元）': [''],
                                        '税后（元）': [''],
                                        '合计经济处理金额（元）': [''],
                                        '主要缴纳金额(税前）': [''],
                                        '主要缴纳金额(税后）': [''],
                                        '扣减当期绩效': [''],
                                        '扣减风险金': [''],
                                        '税后问责': [''],
                                        '执行日期': [''],
                                        '税前执行金额': [''],
                                        '税前待执行金额剩余': [''],
                                        '税后执行金额': [''],
                                        '税后待执行剩余金额': [''],
                                        '合计执行金额': [''],
                                        '未执行到位金额': [''],
                                        '累计执行绩效金额': [''],
                                        '累计执行风险金金额': [''],
                                        '批评教育': [''],
                                        '备注说明': [''],
                                        '会议': ['']
                                    })
                                    file_name = '问责办台账空白模板.xlsx'
                                    template.to_excel(file_name, index=False)
                                    ui.download(file_name)
                                    ui.notify('✅ 模板下载成功', color='green')
                                except Exception as e:
                                    ui.notify(f'❌ 下载失败: {str(e)}', color='red')

                            ui.button('📥 下载空白模板',
                                      on_click=download_template).classes('bg-green-500 text-white')

                            ui.separator()

                            ui.label('📝 填写说明').classes('text-md font-bold')
                            ui.label('所有字段手工录入').classes('text-sm')
                            ui.label('✅ 上传后系统自动计算以下派生字段：').classes('text-sm').style(
                                'font-weight: bold; margin-top: 10px')
                            ui.label(' • 税前执行金额 = 主要缴纳金额(税前）+ 扣减当期绩效 + 扣减风险金').classes(
                                'text-sm').style('margin-left: 20px; margin-top: 5px')
                            ui.label(' • 税前待执行金额剩余 = 经济处理金额（元）- 税前执行金额').classes('text-sm').style(
                                'margin-left: 20px; margin-top: 5px')
                            ui.label(' • 税后执行金额 = 主要缴纳金额(税后）+ 税后问责').classes('text-sm').style(
                                'margin-left: 20px; margin-top: 5px')
                            ui.label(' • 税后待执行剩余金额 = 税后（元）- 税后执行金额').classes('text-sm').style(
                                'margin-left: 20px; margin-top: 5px')
                            ui.label(' • 合计执行金额 = 税前执行金额 + 税后执行金额').classes('text-sm').style(
                                'margin-left: 20px; margin-top: 5px')
                            ui.label(' • 未执行到位金额 = 合计经济处理金额（元）- 合计执行金额').classes('text-sm').style(
                                'margin-left: 20px; margin-top: 5px')

                    # =========================
                    # Tab2 导入台账（重点调整：上传区域的 HTML 按钮）
                    # =========================
                    with ui.tab('导入问责办台账'):
                        ui.label('手工录入所有字段，上传后系统自动计算派生字段').classes('text-md')

                        # 优化上传区域的 HTML：给按钮添加 max-width: 100%，并限制容器宽度
                        upload_html = '''
                        <div style="margin: 20px 0; padding: 20px; border: 3px dashed #9C27B0; border-radius: 8px; background-color: #f3e5f5; width: 100%; box-sizing: border-box;">
                            <input type="file" id="ledgerFile" accept=".xlsx,.xls" style="display:none;">
                            <button id="ledgerChooseBtn"
                                style="padding:12px 14px;background:#FF9800;color:white;border:none;border-radius:4px;max-width: 100%; width: auto; font-weight:bold; box-sizing:border-box;">
                                📁 选择 Excel 文件
                            </button>
                            <button id="ledgerUploadBtn"
                                style="margin-top:10px;padding:12px 14px;background:#9C27B0;color:white;border:none;border-radius:4px;max-width: 100%; width: auto; font-weight:bold; box-sizing:border-box;">
                                📤 上传问责办台账
                            </button>
                            <div id="ledgerFileName" style="margin-top:10px;text-align:center"></div>
                            <div id="ledgerStatus" style="margin-top:10px;text-align:center"></div>
                        </div>
                        '''
                        ui.html(upload_html)

            # =========================
            # 右侧：台账预览（原Tab3）—— 重点修改：限制高度 + 滚动 + 横向滚动
            # =========================
            with ui.column().classes('w-2/3').style('max-height: 80vh; overflow-y: auto;'):  # 👈 限制高度，允许滚动

                ui.label('📊 台账预览（最近50条）').classes('text-lg font-bold')

                conn = get_conn()
                df = pd.read_sql(
                    "SELECT * FROM accountability_ledger ORDER BY 更新时间 DESC LIMIT 50",
                    conn
                )
                conn.close()

                if not df.empty:
                    ui.table.from_pandas(df) \
                        .classes('w-full') \
                        .style('overflow-x:auto; max-height:400px')  # 👈 表格最大高度 + 横向滚动

                    def download_ledger():
                        try:
                            conn = get_conn()
                            df = pd.read_sql(
                                "SELECT * FROM accountability_ledger ORDER BY 更新时间 DESC",
                                conn
                            )
                            conn.close()
                            file_name = '问责办台账.xlsx'
                            df.to_excel(file_name, index=False)
                            ui.download(file_name)
                            ui.notify('✅ 下载成功', color='green')
                        except Exception as e:
                            ui.notify(f'❌ 下载失败: {str(e)}', color='red')

                    ui.button(
                        '📥 下载全部台账',
                        on_click=download_ledger
                    ).classes('bg-blue-500 text-white')
                else:
                    ui.label('暂无数据').classes('text-gray-500')

        ui.separator()
        ui.link('👉 返回', '/').classes('text-blue-600')

# =========================
# 启动应用 - 自动打开浏览器
# =========================
if __name__ == '__main__':
    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open('http://127.0.0.1:10086')


    print("🚀 应用启动中... http://127.0.0.1:10086")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    ui.run(
        host='0.0.0.0',
        port=10086,
        reload=False,
        show=False
    )