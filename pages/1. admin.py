import streamlit as st
import base64
from sqlalchemy import text

st.set_page_config(page_title="Wanchi Admin", layout="centered")
conn = st.connection("postgresql", type="sql")

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("⚙️ Quản trị hệ thống")

if not st.session_state.is_admin:
    st.warning("Vui lòng đăng nhập để tiếp tục.")
    pwd = st.text_input("Mật khẩu Admin", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state.is_admin = True
            st.rerun()
        else:
            st.error("Sai mật khẩu!")
else:
    st.success("Đã đăng nhập quyền quản trị.")
    if st.button("Đăng xuất"):
        st.session_state.is_admin = False
        st.rerun()
    
    st.divider()
    st.subheader("➕ Thêm sản phẩm mới")
    with st.form("add_form"):
        code = st.text_input("Mã SP")
        name = st.text_input("Tên SP")
        size = st.text_input("Kích thước")
        price = st.number_input("Giá", min_value=0)
        desc = st.text_area("Miêu tả chi tiết")
        img_file = st.file_uploader("Tải ảnh", type=['png', 'jpg'])
        
        if st.form_submit_button("Lưu sản phẩm"):
            img_b64 = base64.b64encode(img_file.getvalue()).decode() if img_file else ""
            with conn.session as s:
                s.execute(text("INSERT INTO products (product_code, name, size, description, price, image_data) VALUES (:c, :n, :s, :d, :p, :i)"),
                          {"c": code, "n": name, "s": size, "d": desc, "p": price, "i": img_b64})
                s.commit()
            st.success("Đã lưu thành công!")