import streamlit as st
import pandas as pd
from fpdf import FPDF
from sqlalchemy import text
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import os
import base64
import re

st.set_page_config(page_title="Bán Hàng Wanchi", layout="wide")

if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'cust_name' not in st.session_state:
    st.session_state.cust_name = ""
if 'cust_phone' not in st.session_state:
    st.session_state.cust_phone = ""
if 'saved_order' not in st.session_state:
    st.session_state.saved_order = False

conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

def save_order_to_db(name, phone, total, items_list, file_type, file_bytes):
    try:
        b64_data = base64.b64encode(file_bytes).decode('utf-8')
        items_str = "\n".join([f"- {i['Tên']} (SL: {i['SL']})" for i in items_list])
        
        with conn.session as s:
            s.execute(text("""
                INSERT INTO orders (customer_name, customer_phone, total_amount, order_items, file_type, file_data) 
                VALUES (:n, :p, :t, :it, :ft, :fd)
            """), {"n": name, "p": phone, "t": total, "it": items_str, "ft": file_type, "fd": b64_data})
            s.commit()
    except: pass

st.title("🏭 Cổng Đặt Hàng WANCHI")
tab1, tab2 = st.tabs(["📦 Danh sách sản phẩm", "🛒 Giỏ hàng & Chốt đơn"])

with tab1:
    try:
        # LẤY DỮ LIỆU TỪ BẢNG SẢN PHẨM CÔNG TY ĐỂ ĐỒNG BỘ ẢNH VÀ GIÁ
        df_products = conn.query("SELECT * FROM company_products ORDER BY id", ttl=0)
        
        if df_products.empty:
            st.info("Hiện tại chưa có sản phẩm Công ty nào. Vui lòng vào trang Admin để 'Lên đời' sản phẩm từ kho Đại lý.")
        else:
            # ==========================================
            # KHU VỰC BỘ LỌC TÌM KIẾM
            # ==========================================
            with st.container(border=True):
                st.write("### 🔍 Tìm kiếm sản phẩm")
                col_search_1, col_search_2 = st.columns(2)
                
                search_kw = col_search_1.text_input("🏷️ Tìm theo Mã SP hoặc Tên SP:")
                search_dim = col_search_2.text_input("📏 Tìm theo Kích thước (VD: 240 hoặc 240x160) - Sai số ±5mm:")
                
                if search_kw:
                    kw = search_kw.lower()
                    df_products = df_products[
                        df_products['product_code'].str.lower().str.contains(kw, na=False) |
                        df_products['name'].str.lower().str.contains(kw, na=False)
                    ]
                
                if search_dim:
                    user_dims = [int(n) for n in re.findall(r'\d+', search_dim)]
                    if user_dims:
                        def check_size_tolerance(size_str):
                            if pd.isna(size_str): return False
                            prod_nums = [int(n) for n in re.findall(r'\d+', str(size_str))]
                            used_p = set()
                            for u in user_dims:
                                matched = False
                                for i, p in enumerate(prod_nums):
                                    if i not in used_p and abs(u - p) <= 5:
                                        matched = True
                                        used_p.add(i)
                                        break
                                if not matched: return False
                            return True
                        df_products = df_products[df_products['size'].apply(check_size_tolerance)]

            # ==========================================
            # DANH SÁCH SẢN PHẨM (DẠNG BẢNG NGANG)
            # ==========================================
            if not df_products.empty:
                st.success(f"📦 Tìm thấy {len(df_products)} sản phẩm.")
                for i, row in df_products.iterrows():
                    with st.container(border=True):
                        c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2, 3, 2, 2, 2, 2])
                        
                        with c1:
                            # NÚT XEM THÔNG TIN LẤY ẢNH TỪ DANH SÁCH CÔNG TY
                            with st.popover("🔍 Xem thông tin"):
                                img_url = row['image_data']
                                if img_url and str(img_url).strip() != "":
                                    st.image(img_url, use_container_width=True)
                                else:
                                    st.warning("Sản phẩm này chưa cập nhật ảnh thiết kế.")
                                # Dòng ghi thông tin sản phẩm
                                st.write(f"📂 **Tên sản phẩm:** {row['name']}")

                        # Các cột thông tin khác
                        c2.write(f"**Mã:** {row['product_code']}")
                        c3.write(f"**{row['name']}**")
                        c4.write(f"**KT:** {row['size']}")
                        
                        # Hiển thị giá Công ty (đã chia 0.55 từ Admin)
                        price = row['price_company'] if pd.notna(row['price_company']) else 0
                        c5.write(f"**{int(price):,} đ**")
                        
                        with c6:
                            qty = st.number_input("SL", min_value=1, value=10, step=5, key=f"qty_{row['id']}", label_visibility="collapsed")
                        
                        with c7:
                            if st.button("🛒 Thêm giỏ", key=f"add_{row['id']}", use_container_width=True):
                                code = row['product_code']
                                st.session_state.cart[code] = st.session_state.cart.get(code, 0) + qty
                                st.session_state.saved_order = False
                                st.toast(f"✅ Đã thêm {qty} cái vào giỏ!")
            else:
                st.warning("Không tìm thấy sản phẩm nào phù hợp.")

    except Exception as e:
        st.error(f"Lỗi kết nối cơ sở dữ liệu: {e}")

# ==========================================
# TAB 2: GIỎ HÀNG VÀ CHỐT ĐƠN
# ==========================================
with tab2:
    col_info, col_cart = st.columns([1, 2])
    with col_info:
        st.subheader("📋 Thông tin người mua")
        st.session_state.cust_name = st.text_input("Tên người mua", st.session_state.cust_name)
        st.session_state.cust_phone = st.text_input("Số điện thoại", st.session_state.cust_phone)
    
    with col_cart:
        st.subheader("🛒 Chi tiết đơn hàng")
        if not st.session_state.cart:
            st.info("Giỏ hàng của bạn đang trống.")
        else:
            total_price = 0
            cart_list = []
            # Truy vấn lại để lấy giá mới nhất
            df_prices = conn.query("SELECT product_code, name, price_company FROM company_products", ttl=0)
            for code, qty in st.session_state.cart.items():
                match = df_prices[df_prices['product_code'] == code]
                if not match.empty:
                    p_info = match.iloc[0]
                    price = p_info['price_company'] if pd.notna(p_info['price_company']) else 0
                    line_total = int(price) * qty
                    total_price += line_total
                    cart_list.append({"Mã": code, "Tên": p_info['name'], "SL": qty, "Tiền": line_total})
                    st.write(f"- **{p_info['name']}** (SL: {qty}) : {line_total:,} đ")
            
            st.write(f"### Tổng cộng: {total_price:,} đ")
            
            if st.session_state.cust_name and st.session_state.cust_phone:
                st.divider()
                st.subheader("🎉 Chốt đơn và lưu trữ:")
                # Logic xuất file PDF/JPG và lưu vào DB (Giữ nguyên như bản cũ của bạn)
                # ... (Phần code tạo PDF/Ảnh giống như các bản trước)
