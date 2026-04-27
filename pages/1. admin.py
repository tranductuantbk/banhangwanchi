import streamlit as st
import pandas as pd
from sqlalchemy import text
from fpdf import FPDF
import re
import base64
from datetime import datetime

st.set_page_config(page_title="Wanchi Admin - Quản lý Đại lý & Công ty", layout="wide")
conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

# --- HÀM HỖ TRỢ ---
def convert_drive_link(raw_url):
    if not raw_url: return ""
    match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_url)
    if match: return f"https://drive.google.com/thumbnail?id={match.group(0)}&sz=w1000"
    return raw_url

def export_pdf(df, title_pdf):
    pdf = FPDF()
    pdf.add_page()
    # Chèn font Arial (đảm bảo file arial.ttf có trong thư mục gốc)
    try:
        pdf.add_font("Arial", style="", fname="arial.ttf")
        pdf.set_font("Arial", size=12)
    except:
        pdf.set_font("Helvetica", size=12)
        
    pdf.cell(200, 10, txt=title_pdf, ln=True, align='C')
    pdf.ln(10)
    
    # Header bảng
    pdf.set_font("Arial", size=10)
    pdf.set_fill_color(200, 220, 255)
    cols = df.columns.tolist()
    for col in cols:
        pdf.cell(38, 10, txt=str(col), border=1, fill=True)
    pdf.ln()
    
    # Nội dung bảng
    for _, row in df.iterrows():
        for item in row:
            pdf.cell(38, 10, txt=str(item), border=1)
        pdf.ln()
    return bytes(pdf.output())

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("⚙️ Hệ thống quản lý WANCHI")

if not st.session_state.is_admin:
    pwd = st.text_input("Mật khẩu Admin", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state.is_admin = True
            st.rerun()
        else: st.error("Sai mật khẩu!")
else:
    # --- GIAO DIỆN CHÍNH ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "➕ Thêm SP Đại lý", 
        "📋 Danh sách SP Đại lý", 
        "🏢 Thêm SP Công ty", 
        "📈 Danh sách SP Công ty",
        "📜 Đơn hàng"
    ])

    # 1. THÊM SẢN PHẨM ĐẠI LÝ
    with tab1:
        st.subheader("Nhập sản phẩm Đại lý mới")
        with st.form("agency_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            a_code = c1.text_input("Mã sản phẩm")
            a_name = c2.text_input("Tên sản phẩm")
            a_size = c1.text_input("Kích thước")
            a_price = c2.number_input("Giá Đại lý", min_value=0, step=100)
            if st.form_submit_button("Lưu vào kho Đại lý"):
                with conn.session as s:
                    s.execute(text("INSERT INTO agency_products (product_code, name, size, price_agency) VALUES (:c, :n, :s, :p)"),
                              {"c": a_code, "n": a_name, "s": a_size, "p": a_price})
                    s.commit()
                st.success("Đã thêm sản phẩm Đại lý!")

    # 2. DANH SÁCH SP ĐẠI LÝ
    with tab2:
        st.subheader("Bảng giá Đại lý hiện tại")
        df_a = conn.query("SELECT product_code, name, size, price_agency FROM agency_products", ttl=0)
        if not df_a.empty:
            st.table(df_a)
            pdf_a = export_pdf(df_a, "BANG GIA DAI LY WANCHI")
            st.download_button("📥 Xuất PDF Đại lý", data=pdf_a, file_name="Gia_Dai_Ly_Wanchi.pdf")
        else: st.info("Kho Đại lý trống.")

    # 3. THÊM SẢN PHẨM CÔNG TY (LOGIC TỰ ĐỘNG)
    with tab3:
        st.subheader("Chuyển đổi sản phẩm sang dòng Công ty")
        df_a_select = conn.query("SELECT * FROM agency_products", ttl=0)
        if not df_a_select.empty:
            list_a = {row['id']: f"[{row['product_code']}] {row['name']}" for _, row in df_a_select.iterrows()}
            sel_id = st.selectbox("Chọn sản phẩm từ kho Đại lý", options=list(list_a.keys()), format_func=lambda x: list_a[x])
            
            target = df_a_select[df_a_select['id'] == sel_id].iloc[0]
            price_co = round(float(target['price_agency']) / 0.55, 0)
            
            with st.form("company_form"):
                st.info(f"Mã: {target['product_code']} | Tên: {target['name']}")
                st.write(f"💰 Giá Đại lý: **{int(target['price_agency']):,} đ**")
                st.write(f"🚀 Giá Công ty dự kiến ( / 0.55): **{int(price_co):,} đ**")
                
                raw_img = st.text_input("🔗 Chèn link ảnh thiết kế (Google Drive)")
                
                if st.form_submit_button("Xác nhận thêm vào kho Công ty"):
                    img_final = convert_drive_link(raw_img)
                    with conn.session as s:
                        s.execute(text("""
                            INSERT INTO company_products (product_code, name, size, price_agency, price_company, image_data)
                            VALUES (:c, :n, :s, :pa, :pc, :i)
                            ON CONFLICT (product_code) DO UPDATE SET price_company = :pc, image_data = :i
                        """), {"c": target['product_code'], "n": target['name'], "s": target['size'], 
                               "pa": target['price_agency'], "pc": price_co, "i": img_final})
                        s.commit()
                    st.success("Đã cập nhật kho Công ty!")
        else: st.warning("Cần có sản phẩm Đại lý trước.")

    # 4. DANH SÁCH SẢN PHẨM CÔNG TY
    with tab4:
        st.subheader("Bảng giá Công ty")
        df_c = conn.query("SELECT product_code, name, size, price_company FROM company_products", ttl=0)
        if not df_c.empty:
            st.table(df_c)
            pdf_c = export_pdf(df_c, "BANG GIA CONG TY WANCHI")
            st.download_button("📥 Xuất PDF Công ty", data=pdf_c, file_name="Gia_Cong_Ty_Wanchi.pdf")
        else: st.info("Kho Công ty trống.")

    # 5. LƯU TRỮ ĐƠN HÀNG (Giữ nguyên)
    with tab5:
        st.subheader("Lịch sử đơn hàng")
        df_o = conn.query("SELECT id, customer_name, total_amount, order_date FROM orders ORDER BY order_date DESC", ttl=0)
        if not df_o.empty:
            for _, row in df_o.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    c1.write(f"👤 {row['customer_name']}")
                    c2.write(f"💰 {int(row['total_amount']):,} đ")
                    if c3.button("Xóa", key=f"del_{row['id']}"):
                        with conn.session as s:
                            s.execute(text("DELETE FROM orders WHERE id=:id"), {"id": row['id']})
                            s.commit()
                        st.rerun()
