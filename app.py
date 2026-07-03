from flask import Flask, render_template, request, redirect, url_for, session
from db import query_one, query_all, execute_sql
import os
import time
import db
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'second_hand_platform_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 校验是否为管理员，不是则跳转首页
def check_admin():
    if 'role' not in session or session['role'] != 1:
        return redirect('/')
    return None
# 首页 - 商品列表、分类筛选、关键词搜索
@app.route('/')
def index():
    category = request.args.get('category', '')
    keyword = request.args.get('keyword', '')
    sql = "SELECT g.*, u.username FROM goods g JOIN users u ON g.publisher_id = u.user_id WHERE g.status = 0"
    args = []
    if category:
        sql += " AND g.category COLLATE Chinese_PRC_CI_AS = %s"
        args.append(category)
    if keyword:
        sql += " AND (g.goods_name LIKE %s OR g.description LIKE %s)"
        args.extend([f'%{keyword}%', f'%{keyword}%'])
    sql += " ORDER BY g.publish_time DESC"
    goods_list = query_all(sql, tuple(args))
    return render_template('index.html', goods_list=goods_list)


# 用户登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        sql = "SELECT * FROM users WHERE username = %s AND password = %s"
        user = query_one(sql, (username, password))
        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        return render_template('login.html', msg='用户名或密码错误')
    return render_template('login.html')

import bcrypt

# 注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # 其他字段...

        # 1. 密码加密：生成随机盐 + 哈希
        salt = bcrypt.gensalt()  # 生成随机盐值
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        # 转成字符串存入数据库
        hashed_password_str = hashed_password.decode('utf-8')

        # 2. 把加密后的密码写入数据库，替换原来的明文password
        sql = "INSERT INTO users (username, password, role, ...) VALUES (?, ?, 0, ...)"
        db.execute_sql(sql, (username, hashed_password_str, ...))

        return redirect('/login')
    return render_template('register.html')


# 退出登录
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# 发布商品
@app.route('/publish', methods=['GET', 'POST'])
def publish():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        goods_name = request.form.get('goods_name')
        category = request.form.get('category')
        price = request.form.get('price')
        description = request.form.get('description')
        publisher_id = session['user_id']
        image_path = ''

        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                base_name, ext = os.path.splitext(secure_filename(file.filename))
                # 毫秒级时间戳 + 重名校验，彻底避免图片覆盖
                filename = f"{publisher_id}_{int(time.time() * 1000)}_{base_name}{ext}"
                counter = 1
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
                    filename = f"{publisher_id}_{int(time.time() * 1000)}_{base_name}_{counter}{ext}"
                    counter += 1
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"

        sql = """
        INSERT INTO goods (goods_name, category, price, description, image_path, publisher_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        if execute_sql(sql, (goods_name, category, price, description, image_path, publisher_id)):
            return redirect(url_for('profile'))
        return render_template('publish.html', msg='发布失败，请重试')
    return render_template('publish.html')


# 商品详情
@app.route('/detail/<int:goods_id>')
def detail(goods_id):
    sql = "SELECT g.*, u.username, u.contact FROM goods g JOIN users u ON g.publisher_id = u.user_id WHERE g.goods_id = %s"
    goods = query_one(sql, (goods_id,))
    if not goods:
        return redirect(url_for('index'))
    return render_template('detail.html', goods=goods)


# 个人中心
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user_sql = "SELECT * FROM users WHERE user_id = %s"
    user_info = query_one(user_sql, (user_id,))
    goods_sql = "SELECT * FROM goods WHERE publisher_id = %s ORDER BY publish_time DESC"
    my_goods = query_all(goods_sql, (user_id,))
    return render_template('profile.html', user_info=user_info, my_goods=my_goods)


# 编辑商品信息
@app.route('/goods/edit/<int:goods_id>', methods=['GET', 'POST'])
def goods_edit(goods_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    # 权限校验：仅发布者可编辑
    check_sql = "SELECT * FROM goods WHERE goods_id = %s AND publisher_id = %s"
    goods = query_one(check_sql, (goods_id, user_id))
    if not goods:
        return redirect(url_for('profile'))

    if request.method == 'POST':
        goods_name = request.form.get('goods_name')
        category = request.form.get('category')
        price = request.form.get('price')
        description = request.form.get('description')
        image_path = goods['image_path']  # 默认保留原图

        # 处理新上传的图片
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename) and file.filename.strip() != '':
                base_name, ext = os.path.splitext(secure_filename(file.filename))
                new_filename = f"{user_id}_{int(time.time() * 1000)}_{base_name}{ext}"
                counter = 1
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)):
                    new_filename = f"{user_id}_{int(time.time() * 1000)}_{base_name}_{counter}{ext}"
                    counter += 1
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
                image_path = f"uploads/{new_filename}"

        # 更新数据库
        update_sql = """
        UPDATE goods 
        SET goods_name = %s, category = %s, price = %s, description = %s, image_path = %s
        WHERE goods_id = %s
        """
        if execute_sql(update_sql, (goods_name, category, price, description, image_path, goods_id)):
            return redirect(url_for('profile'))
        return render_template('edit.html', goods=goods, msg='修改失败，请重试')

    # GET请求：加载原有数据
    return render_template('edit.html', goods=goods)


# 标记商品已售出（下架）
@app.route('/goods/off/<int:goods_id>')
def goods_off(goods_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    check_sql = "SELECT * FROM goods WHERE goods_id = %s AND publisher_id = %s"
    goods = query_one(check_sql, (goods_id, user_id))
    if not goods:
        return redirect(url_for('profile'))
    update_sql = "UPDATE goods SET status = 1 WHERE goods_id = %s"
    execute_sql(update_sql, (goods_id,))
    return redirect(url_for('profile'))


# 删除商品
@app.route('/goods/delete/<int:goods_id>')
def goods_delete(goods_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    check_sql = "SELECT * FROM goods WHERE goods_id = %s AND publisher_id = %s"
    goods = query_one(check_sql, (goods_id, user_id))
    if not goods:
        return redirect(url_for('profile'))
    delete_sql = "DELETE FROM goods WHERE goods_id = %s"
    execute_sql(delete_sql, (goods_id,))
    return redirect(url_for('profile'))


# 管理员后台首页
@app.route('/admin')
def admin_index():
    # 权限校验
    res = check_admin()
    if res:
        return res

    # 查询所有商品、所有用户
    goods_sql = "SELECT g.*, u.username FROM goods g JOIN users u ON g.publisher_id = u.user_id ORDER BY g.publish_time DESC"
    all_goods = query_all(goods_sql)

    user_sql = "SELECT * FROM users ORDER BY create_time DESC"
    all_users = query_all(user_sql)

    return render_template('admin.html', all_goods=all_goods, all_users=all_users)


# 管理员删除任意商品
@app.route('/admin/delete_goods/<int:goods_id>')
def admin_delete_goods(goods_id):
    res = check_admin()
    if res:
        return res

    sql = "DELETE FROM goods WHERE goods_id = %s"
    execute_sql(sql, (goods_id,))
    return redirect('/admin')


# 管理员删除任意用户
@app.route('/admin/delete_user/<int:user_id>')
def admin_delete_user(user_id):
    res = check_admin()
    if res:
        return res

    # 先删除该用户发布的所有商品，再删用户
    execute_sql("DELETE FROM goods WHERE publisher_id = %s", (user_id,))
    execute_sql("DELETE FROM users WHERE user_id = %s", (user_id,))
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)