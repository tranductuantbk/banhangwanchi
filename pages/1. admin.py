import streamlit as st
import pandas as pd
from sqlalchemy import text
import re
import base64

st.set_page_config(page_title="Wanchi Admin", layout="wide")

# Kết nối CSDL Neon (Chống ngủ đông)
conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

# --- HÀM TỰ ĐỘNG CHUYỂN ĐỔI LINK DRIVE (ĐÃ NÂNG CẤP CHỐNG CHẶN) ---
def convert_drive_link(raw_url):
    if not raw_url:
        return ""
    if "/folders/" in raw_url:
        st.error("⚠️ Bạn đang dán link THƯ MỤC. Hãy mở to ảnh rồi lấy link lại nhé!")
        return raw_url
    match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_url)
    if match:
        # SỬ DỤNG LINK THUMBNAIL CHUYÊN DỤNG CỦA GOOGLE DRIVE
        return f"https://drive.google.com/thumbnail?id={match.group(0)}&sz=w1000"
    return raw_url

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("⚙️ Quản trị hệ thống Wanchi")

# --- ĐĂNG NHẬP ---
if not st.session_state.is_admin:
    pwd = st.text_input("Mật khẩu Admin", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state.is_admin = True
            st.rerun()
        else:
            st.error("Sai mật khẩu!")
else:
    col_acc, col_logout = st.columns([8, 1])
    col_acc.success("Quyền Quản trị viên: Đang hoạt động")
    if col_logout.button("Đăng xuất"):
        st.session_state.is_admin = False
        st.rerun()

    st.divider()
    tab_add, tab_edit = st.tabs(["➕ Thêm Sản Phẩm Mới", "🛠 Chỉnh sửa / Xóa"])

    # ==========================================
    # TAB 1: THÊM SẢN PHẨM
    # ==========================================
    with tab_add:
        with st.form("add_form", clear_on_submit=True):
            st.subheader("Thông tin sản phẩm")
            c1, c2 = st.columns(2)
            code = c1.text_input("Mã SP (Ví dụ: CW-XE-40)")
            name = c2.text_input("Tên sản phẩm")
            
            c3, c4 = st.columns(2)
            size = c3.text_input("Kích thước")
            price = c4.number_input("Giá bán (VNĐ)", min_value=0, step=500)
            
            desc = st.text_area("Mô tả chi tiết")
            
            raw_img_url = st.text_input("🔗 Dán link chia sẻ từ Google Drive vào đây (Hệ thống tự xử lý)")
            
            if st.form_submit_button("💾 LƯU SẢN PHẨM"):
                final_link = convert_drive_link(raw_img_url)
                
                with conn.session as s:
                    s.execute(text("""
                        INSERT INTO products (product_code, name, size, description, price, image_data) 
                        VALUES (:c, :n, :s, :d, :p, :i)
                    """), {"c": code, "n": name, "s": size, "d": desc, "p": price, "i": final_link})
                    s.commit()
                st.success(f"✅ Đã thêm sản phẩm {name} thành công!")

    # ==========================================
    # TAB 2: SỬA / XÓA SẢN PHẨM
    # ==========================================
    with tab_edit:
        df_admin = conn.query("SELECT * FROM products ORDER BY id DESC", ttl=0)
        
        if df_admin.empty:
            st.info("Kho hàng đang trống.")
        else:
            list_sp = {row['id']: f"[{row['product_code']}] {row['name']}" for _, row in df_admin.iterrows()}
            sel_id = st.selectbox("Chọn sản phẩm cần chỉnh sửa", options=list(list_sp.keys()), format_func=lambda x: list_sp[x])
            
            if sel_id:
                sp = df_admin[df_admin['id'] == sel_id].iloc[0]
                
                with st.form("edit_form"):
                    st.write(f"--- Đang chỉnh sửa: **{sp['name']}** ---")
                    ec1, ec2 = st.columns(2)
                    e_code = ec1.text_input("Mã SP", value=sp['product_code'])
                    e_name = ec2.text_input("Tên sản phẩm", value=sp['name'])
                    
                    ec3, ec4 = st.columns(2)
                    e_size = ec3.text_input("Kích thước", value=sp['size'] if pd.notna(sp['size']) else "")
                    e_price = ec4.number_input("Giá bán", value=int(sp['price'] if pd.notna(sp['price']) else 0), step=500)
                    
                    e_desc = st.text_area("Mô tả", value=sp['description'] if pd.notna(sp['description']) else "")
                    
                    # Ô DÁN LINK SỬA
                    e_raw_link = st.text_input("Link ảnh mới (Để trống nếu giữ ảnh cũ)", value=sp['image_data'] if pd.notna(sp['image_data']) else "")
                    
                    col_save, col_del = st.columns(2)
                    
                    if col_save.form_submit_button("💾 CẬP NHẬT THAY ĐỔI", type="primary"):
                        e_final_link = convert_drive_link(e_raw_link)
                        with conn.session as s:
                            s.execute(text("""
                                UPDATE products SET product_code=:c, name=:n, size=:s, price=:p, description=:d, image_data=:i 
                                WHERE id=:id
                            """), {"c": e_code, "n": e_name, "s": e_size, "p": e_price, "d": e_desc, "i": e_final_link, "id": sel_id})
                            s.commit()
                        st.success("Đã cập nhật thông tin!")
                        st.rerun()
                        
                    if col_del.form_submit_button("🗑️ XÓA SẢN PHẨM NÀY"):
                        with conn.session as s:
                            s.execute(text("DELETE FROM products WHERE id=:id"), {"id": sel_id})
                            s.commit()
                        st.warning("Đã xóa sản phẩm khỏi kho hàng.")
                        st.rerun()
