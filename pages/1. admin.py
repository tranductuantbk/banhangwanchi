import streamlit as st
import base64
import pandas as pd
from sqlalchemy import text

st.set_page_config(page_title="Wanchi Admin", layout="wide")
conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("⚙️ Quản trị hệ thống Wanchi")

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
    col1, col2 = st.columns([8, 1])
    col1.success("Đã đăng nhập quyền quản trị.")
    if col2.button("Đăng xuất"):
        st.session_state.is_admin = False
        st.rerun()
    st.divider()
    
    # CHỈ GIỮ LẠI 2 TABS CHÍNH
    tab_add, tab_edit = st.tabs(["➕ Thêm SP", "🛠 Sửa / Xóa SP"])
    
    with tab_add:
        with st.form("add_form", clear_on_submit=True):
            code = st.text_input("Mã SP")
            name = st.text_input("Tên SP")
            size = st.text_input("Kích thước")
            price = st.number_input("Giá", min_value=0)
            desc = st.text_area("Miêu tả chi tiết")
            img_link = st.text_input("🔗 Link ảnh trực tuyến (Copy địa chỉ hình ảnh trên mạng dán vào đây)")
            
            if st.form_submit_button("Lưu sản phẩm"):
                with conn.session as s:
                    s.execute(text("INSERT INTO products (product_code, name, size, description, price, image_data) VALUES (:c, :n, :s, :d, :p, :i)"),
                              {"c": code, "n": name, "s": size, "d": desc, "p": price, "i": img_link})
                    s.commit()
                st.success("Đã thêm thành công!")

    with tab_edit:
        df_admin = conn.query("SELECT * FROM products ORDER BY id", ttl=0)
        if df_admin.empty:
            st.info("Hiện chưa có sản phẩm nào.")
        else:
            prod_dict = {row['id']: f"[{row['product_code']}] {row['name']}" for _, row in df_admin.iterrows()}
            selected_id = st.selectbox("📌 Chọn sản phẩm", options=list(prod_dict.keys()), format_func=lambda x: prod_dict[x])
            if selected_id:
                prod = df_admin[df_admin['id'] == selected_id].iloc[0]
                with st.form("edit_form"):
                    st.write(f"Đang sửa: **{prod['name']}**")
                    e_code = st.text_input("Mã SP", value=prod['product_code'])
                    e_name = st.text_input("Tên SP", value=prod['name'])
                    e_size = st.text_input("Kích thước", value=prod['size'] if pd.notna(prod['size']) else "")
                    e_price = st.number_input("Giá", min_value=0, value=int(prod['price'] if pd.notna(prod['price']) else 0))
                    e_desc = st.text_area("Miêu tả", value=prod['description'] if pd.notna(prod['description']) else "")
                    e_img_link = st.text_input("🔗 Link ảnh", value=prod['image_data'] if pd.notna(prod['image_data']) else "")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                            query = text("UPDATE products SET product_code=:c, name=:n, size=:s, price=:p, description=:d, image_data=:i WHERE id=:id")
                            params = {"c": e_code, "n": e_name, "s": e_size, "p": e_price, "d": e_desc, "i": e_img_link, "id": selected_id}
                            with conn.session as s:
                                s.execute(query, params)
                                s.commit()
                            st.success("Đã cập nhật!")
                            st.rerun()
                    with c2:
                        if st.form_submit_button("🗑️ Xóa SP"):
                            with conn.session as s:
                                s.execute(text("DELETE FROM products WHERE id=:id"), {"id": selected_id})
                                s.commit()
                            st.success("Đã xóa!")
                            st.rerun()
