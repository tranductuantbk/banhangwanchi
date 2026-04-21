import streamlit as st
import base64
import pandas as pd
from sqlalchemy import text

st.set_page_config(page_title="Wanchi Admin", layout="centered")
conn = st.connection("postgresql", type="sql")

if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("⚙️ Quản trị hệ thống Wanchi")

# --- XÁC THỰC ĐĂNG NHẬP ---
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
    
    # --- CHIA TABS CHỨC NĂNG ---
    tab_add, tab_edit = st.tabs(["➕ Thêm sản phẩm mới", "🛠 Sửa / Xóa sản phẩm"])
    
    # ==========================================
    # KHU VỰC 1: THÊM SẢN PHẨM MỚI
    # ==========================================
    with tab_add:
        with st.form("add_form", clear_on_submit=True):
            code = st.text_input("Mã SP")
            name = st.text_input("Tên SP")
            size = st.text_input("Kích thước")
            price = st.number_input("Giá", min_value=0)
            desc = st.text_area("Miêu tả chi tiết")
            img_file = st.file_uploader("Tải ảnh", type=['png', 'jpg', 'jpeg'])
            
            if st.form_submit_button("Lưu sản phẩm"):
                img_b64 = base64.b64encode(img_file.getvalue()).decode() if img_file else ""
                with conn.session as s:
                    s.execute(text("INSERT INTO products (product_code, name, size, description, price, image_data) VALUES (:c, :n, :s, :d, :p, :i)"),
                              {"c": code, "n": name, "s": size, "d": desc, "p": price, "i": img_b64})
                    s.commit()
                st.success("Đã thêm thành công! Dữ liệu đã được cập nhật ra trang khách hàng.")

    # ==========================================
    # KHU VỰC 2: CHỈNH SỬA VÀ XÓA
    # ==========================================
    with tab_edit:
        # Lấy dữ liệu mới nhất từ CSDL
        df_admin = conn.query("SELECT * FROM products ORDER BY id", ttl=0)
        
        if df_admin.empty:
            st.info("Hiện chưa có sản phẩm nào trong kho.")
        else:
            # Tạo danh sách thả xuống để chọn sản phẩm
            prod_dict = {row['id']: f"[{row['product_code']}] {row['name']}" for _, row in df_admin.iterrows()}
            selected_id = st.selectbox("📌 Chọn sản phẩm cần thao tác", options=list(prod_dict.keys()), format_func=lambda x: prod_dict[x])
            
            if selected_id:
                # Lấy thông tin của sản phẩm đang được chọn
                prod = df_admin[df_admin['id'] == selected_id].iloc[0]
                
                with st.form("edit_form"):
                    st.write(f"Đang chỉnh sửa: **{prod['name']}**")
                    
                    e_code = st.text_input("Mã SP", value=prod['product_code'])
                    e_name = st.text_input("Tên SP", value=prod['name'])
                    e_size = st.text_input("Kích thước", value=prod['size'] if pd.notna(prod['size']) else "")
                    e_price = st.number_input("Giá", min_value=0, value=int(prod['price'] if pd.notna(prod['price']) else 0))
                    e_desc = st.text_area("Miêu tả", value=prod['description'] if pd.notna(prod['description']) else "")
                    
                    st.caption("💡 Nếu không tải ảnh mới, hệ thống sẽ giữ nguyên ảnh cũ của sản phẩm.")
                    e_img = st.file_uploader("Tải ảnh thay thế (Tùy chọn)", type=['png', 'jpg', 'jpeg'])
                    
                    # Chia 2 nút Sửa và Xóa ra 2 cột
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                            if e_img is not None:
                                # Cập nhật toàn bộ kèm ảnh mới
                                e_img_b64 = base64.b64encode(e_img.getvalue()).decode()
                                query = text("UPDATE products SET product_code=:c, name=:n, size=:s, price=:p, description=:d, image_data=:i WHERE id=:id")
                                params = {"c": e_code, "n": e_name, "s": e_size, "p": e_price, "d": e_desc, "i": e_img_b64, "id": selected_id}
                            else:
                                # Cập nhật thông tin, giữ nguyên ảnh cũ
                                query = text("UPDATE products SET product_code=:c, name=:n, size=:s, price=:p, description=:d WHERE id=:id")
                                params = {"c": e_code, "n": e_name, "s": e_size, "p": e_price, "d": e_desc, "id": selected_id}
                            
                            with conn.session as s:
                                s.execute(query, params)
                                s.commit()
                            st.success("Cập nhật thành công!")
                            st.rerun() # Tải lại trang để thấy dữ liệu mới
                            
                    with col2:
                        if st.form_submit_button("🗑️ Xóa sản phẩm này"):
                            with conn.session as s:
                                s.execute(text("DELETE FROM products WHERE id=:id"), {"id": selected_id})
                                s.commit()
                            st.success("Đã xóa sản phẩm!")
                            st.rerun()
