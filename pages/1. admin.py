import streamlit as st
import pandas as pd
from sqlalchemy import text
import re
import base64

st.set_page_config(page_title="Wanchi Admin", layout="wide")

# Kết nối CSDL Neon (Chống ngủ đông)
conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

# --- HÀM TỰ ĐỘNG CHUYỂN ĐỔI LINK DRIVE CHỐNG CHẶN ẢNH ---
def convert_drive_link(raw_url):
    if not raw_url:
        return ""
    if "/folders/" in raw_url:
        st.error("⚠️ Bạn đang dán link THƯ MỤC. Hãy mở to ảnh rồi lấy link lại nhé!")
        return raw_url
    match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_url)
    if match:
        # Sử dụng link thumbnail để hiển thị ảnh ổn định trên web
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
    
    # 3 TABS CHỨC NĂNG
    tab_add, tab_edit, tab_orders = st.tabs(["➕ Thêm SP", "🛠 Sửa / Xóa SP", "📜 Lưu trữ đơn hàng"])

    # ==========================================
    # TAB 1: THÊM SẢN PHẨM
    # ==========================================
    with tab_add:
        with st.form("add_form", clear_on_submit=True):
            st.subheader("Thông tin sản phẩm mới")
            c1, c2 = st.columns(2)
            code = c1.text_input("Mã SP")
            name = c2.text_input("Tên sản phẩm")
            
            c3, c4 = st.columns(2)
            size = c3.text_input("Kích thước")
            price = c4.number_input("Giá bán (VNĐ)", min_value=0, step=500)
            
            desc = st.text_area("Mô tả chi tiết")
            raw_img_url = st.text_input("🔗 Link ảnh Google Drive (Dán thẳng link chia sẻ vào đây)")
            
            if st.form_submit_button("💾 LƯU SẢN PHẨM"):
                final_link = convert_drive_link(raw_img_url)
                with conn.session as s:
                    s.execute(text("""
                        INSERT INTO products (product_code, name, size, description, price, image_data) 
                        VALUES (:c, :n, :s, :d, :p, :i)
                    """), {"c": code, "n": name, "s": size, "d": desc, "p": price, "i": final_link})
                    s.commit()
                st.success(f"✅ Đã thêm sản phẩm {name}!")

    # ==========================================
    # TAB 2: CHỈNH SỬA / XÓA SẢN PHẨM
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
                    st.write(f"Đang sửa: **{sp['name']}**")
                    e_code = st.text_input("Mã SP", value=sp['product_code'])
                    e_name = st.text_input("Tên sản phẩm", value=sp['name'])
                    e_size = st.text_input("Kích thước", value=sp['size'] if pd.notna(sp['size']) else "")
                    e_price = st.number_input("Giá", value=int(sp['price'] if pd.notna(sp['price']) else 0))
                    e_desc = st.text_area("Mô tả", value=sp['description'] if pd.notna(sp['description']) else "")
                    e_raw_link = st.text_input("Link ảnh", value=sp['image_data'] if pd.notna(sp['image_data']) else "")
                    
                    c_s, c_d = st.columns(2)
                    if c_s.form_submit_button("💾 CẬP NHẬT", type="primary"):
                        e_final = convert_drive_link(e_raw_link)
                        with conn.session as s:
                            s.execute(text("""
                                UPDATE products SET product_code=:c, name=:n, size=:s, price=:p, description=:d, image_data=:i 
                                WHERE id=:id
                            """), {"c": e_code, "n": e_name, "s": e_size, "p": e_price, "d": e_desc, "i": e_final, "id": sel_id})
                            s.commit()
                        st.success("Đã cập nhật!")
                        st.rerun()
                    if c_d.form_submit_button("🗑️ XÓA SP"):
                        with conn.session as s:
                            s.execute(text("DELETE FROM products WHERE id=:id"), {"id": sel_id})
                            s.commit()
                        st.rerun()

    # ==========================================
    # TAB 3: LƯU TRỮ ĐƠN HÀNG (CÓ NÚT XÓA ĐƠN)
    # ==========================================
    with tab_orders:
        st.subheader("📜 Danh sách đơn hàng khách đã chốt")
        try:
            df_orders = conn.query("SELECT * FROM orders ORDER BY order_date DESC", ttl=0)
            
            if df_orders.empty:
                st.info("Chưa có đơn hàng nào được lưu.")
            else:
                for i, row in df_orders.iterrows():
                    with st.container(border=True):
                        col_info, col_date, col_action = st.columns([2, 2, 1.5])
                        
                        with col_info:
                            st.write(f"👤 **{row['customer_name']}**")
                            st.write(f"📞 {row['customer_phone']}")
                        
                        with col_date:
                            time_str = row['order_date'].strftime("%d/%m/%Y %H:%M")
                            st.write(f"⏰ {time_str}")
                            st.write(f"💰 **{int(row['total_amount']):,} đ**")
                        
                        with col_action:
                            # Nút tải lại file đơn hàng
                            if pd.notna(row['file_data']) and row['file_data']:
                                try:
                                    file_bytes = base64.b64decode(row['file_data'])
                                    ext = row['file_type'] if pd.notna(row['file_type']) else "pdf"
                                    mime = "image/jpeg" if ext == "jpg" else "application/pdf"
                                    
                                    st.download_button(
                                        label=f"📥 Tải lại (.{ext})",
                                        data=file_bytes,
                                        file_name=f"Don_Wanchi_{row['customer_name']}.{ext}",
                                        mime=mime,
                                        key=f"re_dl_{row['id']}"
                                    )
                                except:
                                    st.write("*(Lỗi file)*")
                            
                            # NÚT XÓA ĐƠN HÀNG
                            if st.button("🗑️ Xóa đơn hàng", key=f"del_order_{row['id']}", type="secondary"):
                                with conn.session as s:
                                    s.execute(text("DELETE FROM orders WHERE id=:id"), {"id": row['id']})
                                    s.commit()
                                st.rerun()
                        
                        with st.expander("🔍 Chi tiết sản phẩm"):
                            st.text(row['order_items'])
        except Exception as e:
            st.error(f"Lỗi: {e}")
