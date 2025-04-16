from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
from functools import wraps
import os
import time
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'  # Обратите внимание на 3 слэша
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Добавьте секретный ключ
app.config['UPLOAD_FOLDER'] = 'uploads/'  # Папка для загрузки аватаров

# Добавьте сразу после создания приложения app
app.config['UPLOAD_FOLDER'] = 'static/uploads'
# Создаем папку, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Инициализация SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

db = SQLAlchemy(app)

# Модель пользователя (расширенная)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    avatar = db.Column(db.String(200))  # путь к файлу аватара
    nickname = db.Column(db.String(50))  # добавьте это поле
    birthdate = db.Column(db.Date)       # добавьте это поле
    status = db.Column(db.String(100))   # добавьте это поле
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Добавьте метод для установки пароля
    def set_password(self, password):
        self.password = password  # В идеале здесь должно быть хеширование пароля
    
    # Связи с другими таблицами
    sent_messages = db.relationship('Message', backref='sender', foreign_keys='Message.sender_id')
    received_messages = db.relationship('Message', backref='recipient', foreign_keys='Message.recipient_id')
    group_memberships = db.relationship('GroupMember', backref='user')
    friendships = db.relationship('Friendship', 
                                  foreign_keys='Friendship.user_id',
                                  backref=db.backref('user', lazy='joined'),
                                  lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.id}>'

# Модель сообщений
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    content = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь с вложениями
    attachments = db.relationship('Attachment', backref='message')
    
    def __repr__(self):
        return f'<Message {self.id}>'

# Модель групповых чатов
class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    avatar = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    members = db.relationship('GroupMember', backref='group')
    messages = db.relationship('Message', backref='group')
    creator = db.relationship('User', foreign_keys=[creator_id])
    
    def __repr__(self):
        return f'<Group {self.name}>'

# Промежуточная таблица для связи пользователей с группами
class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GroupMember {self.user_id} in {self.group_id}>'

# Модель для хранения вложений
class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'))
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)  # размер в байтах
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Attachment {self.file_name}>'

# Add a new model for friend relationships
class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define a unique constraint to prevent duplicate friendships
    __table_args__ = (db.UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),)
    
    def __repr__(self):
        return f'<Friendship {self.user_id} -> {self.friend_id}>'

# Декоратор для проверки аутентификации пользователя
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему для доступа к этой странице', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Функция для получения текущего пользователя из сессии
def get_current_user():
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None

@app.route('/register', methods=['POST', 'GET'])
def register():
    # Перенаправляем, если пользователь уже вошел в систему
    # if 'user_id' in session:
    #     return redirect(url_for('mainWindow'))
        
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        # Исправлено - проверяем подтверждение пароля
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return "Пароли не совпадают"
            
        # Проверка, существует ли пользователь с таким email
        existing_user = User.query.filter_by(email=email).first()
        if (existing_user):
            return "Пользователь с таким email уже существует"
            
        user = User(name=name, email=email, password=password)
        try:
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('mainWindow'))
        except Exception as e:
            db.session.rollback()
            return f"При добавлении пользователя произошла ошибка: {str(e)}"
    else:   
        return render_template("register.html")
    

# Добавьте функцию логина
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Перенаправляем, если пользователь уже вошел в систему
    if 'user_id' in session:
        return redirect(url_for('mainWindow'))
        
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        captcha = 'captcha' in request.form
        
        if not captcha:
            error = "Пожалуйста, подтвердите что вы не робот"
            return render_template('login.html', error=error)
        
        user = User.query.filter((User.name == username) | (User.email == username)).first()
        
        if user and user.password == password:
            # Сохраняем ID пользователя в сессии
            session['user_id'] = user.id
            return redirect(url_for('mainWindow'))
        else:
            error = "Неверное имя пользователя или пароль"
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    # Удаляем данные пользователя из сессии
    session.pop('user_id', None)
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('login'))

@app.route('/mainWindow')
@login_required
def mainWindow():
    current_user = get_current_user()
    
    # Get the friends of the current user
    friends = User.query.join(Friendship, Friendship.friend_id == User.id)\
                       .filter(Friendship.user_id == current_user.id).all()
                       
    # Get other users who are not friends (for searching/adding)
    other_users = User.query.filter(User.id != current_user.id)\
                          .filter(~User.id.in_([f.id for f in friends])).all()
                          
    # Get groups in which the user is a member
    user_groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    
    return render_template("mainWindow.html", 
                          current_user=current_user,
                          friends=friends, 
                          all_users=other_users,
                          user_groups=user_groups)

@app.route('/settings')
@login_required
def settings():
    current_user = get_current_user()
    return render_template("settings.html", current_user=current_user)

@app.route('/myprofile')
@login_required
def myprofile():
    current_user = get_current_user()
    return render_template("myprofile.html", current_user=current_user)

@app.route('/invitefriend')
@login_required
def invitefriend():
    current_user = get_current_user()
    return render_template("invitefriend.html", current_user=current_user)

@app.route('/newgroup')
@login_required
def newgroup():
    current_user = get_current_user()
    return render_template("newgroup.html", current_user=current_user)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        current_user = get_current_user()  # Получаем текущего пользователя
        
        # Остальной код без изменений
        nickname = request.form.get('nickname')
        name = request.form.get('name')
        birthdate = request.form.get('birthdate')
        status = request.form.get('status')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Проверка наличия обязательного поля никнейма
        if not nickname:
            return jsonify({'success': False, 'message': 'Никнейм обязателен!'}), 400
            
        # Обновление данных пользователя в базе
        user = db.session.get(User, current_user.id)
        user.nickname = nickname
        user.name = name
        if birthdate:
            try:
                # Convert string date to Python date object
                user.birthdate = datetime.strptime(birthdate, '%Y-%m-%d').date()
            except Exception as e:
                print(f"Error converting birthdate: {e}")
                # Keep the current birthdate if conversion fails
                pass
        user.status = status
        user.email = email
        
        # Обновление пароля, если указан новый
        if password:
            user.set_password(password)
            
        # Обработка аватара, если загружен
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file.filename != '':
                # Сохранение файла
                filename = secure_filename(f"avatar_{current_user.id}_{int(time.time())}{os.path.splitext(avatar_file.filename)[1]}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                avatar_file.save(filepath)
                
                # Обновление пути к аватару в базе данных
                user.avatar = f"uploads/{filename}"
                
        # Сохранение изменений в базе данных
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Профиль успешно обновлен!'})
    except Exception as e:
        db.session.rollback()
        print(f"Profile update error: {str(e)}")  # Add debug logging
        return jsonify({'success': False, 'message': f'Ошибка обновления профиля: {str(e)}'}), 500

@app.route('/add_friend', methods=['POST'])
@login_required
def add_friend():
    try:
        current_user = get_current_user()
        data = request.get_json()
        identifier = data.get('identifier', '')
        
        if not identifier:
            return jsonify({'success': False, 'message': 'Name or email is required'}), 400
        
        # Look for the user by name or email
        friend = User.query.filter((User.name == identifier) | 
                                   (User.email == identifier) | 
                                   (User.nickname == identifier)).first()
        
        if not friend:
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
        if friend.id == current_user.id:
            return jsonify({'success': False, 'message': 'Cannot add yourself as a friend'}), 400
        
        # Check if they are already friends
        existing_friendship = Friendship.query.filter_by(
            user_id=current_user.id, friend_id=friend.id
        ).first()
        
        if existing_friendship:
            return jsonify({'success': False, 'message': f'You are already friends with {friend.name}'}), 400
        
        # Create the friendship (bidirectional)
        friendship1 = Friendship(user_id=current_user.id, friend_id=friend.id)
        friendship2 = Friendship(user_id=friend.id, friend_id=current_user.id)
        
        db.session.add(friendship1)
        db.session.add(friendship2)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully added {friend.name} as a friend',
            'friend': {
                'id': friend.id,
                'name': friend.name,
                'email': friend.email,
                'nickname': friend.nickname,
                'avatar': friend.avatar
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Add friend error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error adding friend: {str(e)}'}), 500

@app.route('/get_friends', methods=['GET'])
@login_required
def get_friends():
    try:
        current_user = get_current_user()
        
        # Get the user's friends
        friends = User.query.join(Friendship, Friendship.friend_id == User.id)\
                          .filter(Friendship.user_id == current_user.id).all()
        
        friends_list = []
        for friend in friends:
            friends_list.append({
                'id': friend.id,
                'name': friend.name,
                'nickname': friend.nickname,
                'email': friend.email,
                'avatar': friend.avatar if friend.avatar else None
            })
        
        return jsonify({
            'success': True,
            'friends': friends_list
        })
        
    except Exception as e:
        print(f"Get friends error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        name = data.get('name', '').strip()
        member_ids = data.get('members', [])
        
        if not name:
            return jsonify({'success': False, 'message': 'Group name is required'}), 400
            
        if len(member_ids) == 0:
            return jsonify({'success': False, 'message': 'At least one member must be selected'}), 400
        
        # Create new group
        new_group = Group(
            name=name,
            creator_id=current_user.id
        )
        db.session.add(new_group)
        db.session.flush()  # This assigns an ID to the new_group
        
        # Add the current user as admin
        creator_member = GroupMember(
            user_id=current_user.id,
            group_id=new_group.id,
            is_admin=True
        )
        db.session.add(creator_member)
        
        # Add selected members
        for member_id in member_ids:
            # Skip if the member ID is the same as current user (already added as admin)
            if member_id == current_user.id:
                continue
                
            member = GroupMember(
                user_id=member_id,
                group_id=new_group.id,
                is_admin=False
            )
            db.session.add(member)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Group "{name}" created successfully',
            'group': {
                'id': new_group.id,
                'name': new_group.name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Create group error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error creating group: {str(e)}'}), 500

@app.route('/get_group_details/<int:group_id>', methods=['GET'])
@login_required
def get_group_details(group_id):
    try:
        current_user = get_current_user()
        
        # Check if the user is a member of the group
        member_info = GroupMember.query.filter_by(
            user_id=current_user.id, 
            group_id=group_id
        ).first()
        
        if not member_info:
            return jsonify({'success': False, 'message': 'You are not a member of this group'}), 403
            
        # Get group details
        group = db.session.get(Group, group_id)
        if not group:
            return jsonify({'success': False, 'message': 'Group not found'}), 404
        
        # Check if the current user is the creator
        is_creator = (group.creator_id == current_user.id)
        # Check if the user is an admin
        is_admin = member_info.is_admin
        
        # Get members list with additional information
        members = User.query.join(GroupMember).filter(GroupMember.group_id == group_id).all()
        member_list = []
        
        for member in members:
            member_status = GroupMember.query.filter_by(user_id=member.id, group_id=group_id).first()
            member_data = {
                'id': member.id,
                'name': member.name,
                'nickname': member.nickname,
                'avatar': member.avatar,
                'is_admin': member_status.is_admin,
                'is_creator': (member.id == group.creator_id)
            }
            member_list.append(member_data)
        
        return jsonify({
            'success': True,
            'group': {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'avatar': group.avatar,
                'is_creator': is_creator,
                'is_admin': is_admin,
                'creator_id': group.creator_id,
                'members': member_list
            }
        })
    
    except Exception as e:
        print(f"Get group details error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/search_users', methods=['GET'])
@login_required
def search_users():
    try:
        current_user = get_current_user()
        query = request.args.get('q', '')
        
        if not query:
            return jsonify({'success': False, 'message': 'Missing search query'}), 400
            
        # Поиск пользователей
        users = User.query.filter(
            User.id != current_user.id,
            (User.name.ilike(f'%{query}%') | 
             User.email.ilike(f'%{query}%') | 
             User.nickname.ilike(f'%{query}%'))
        ).all()
        
        # Формируем список найденных пользователей
        users_list = []
        for user in users:
            # Проверяем, является ли пользователь другом
            is_friend = Friendship.query.filter_by(
                user_id=current_user.id, 
                friend_id=user.id
            ).first() is not None
            
            users_list.append({
                'id': user.id,
                'name': user.nickname or user.name,
                'email': user.email,
                'avatar': user.avatar,
                'is_friend': is_friend
            })
        
        # Поиск групп
        groups = Group.query.join(GroupMember).filter(
            GroupMember.user_id == current_user.id,
            Group.name.ilike(f'%{query}%')
        ).all()
        
        # Формируем список найденных групп
        groups_list = []
        for group in groups:
            groups_list.append({
                'id': group.id,
                'name': group.name,
                'avatar': group.avatar,
                'member_count': GroupMember.query.filter_by(group_id=group.id).count()
            })
            
        return jsonify({
            'success': True,
            'users': users_list,
            'groups': groups_list
        })
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/add_group_member', methods=['POST'])
@login_required
def add_group_member():
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        
        if not group_id or not user_id:
            return jsonify({'success': False, 'message': 'Missing group or user ID'}), 400
            
        # Verify the current user is a member of the group (no admin check)
        member_info = GroupMember.query.filter_by(
            user_id=current_user.id,
            group_id=group_id
        ).first()
        
        if not member_info:
            return jsonify({'success': False, 'message': 'You are not a member of this group'}), 403
        
        # Check if the user to add exists
        user_to_add = db.session.get(User, user_id)
        if not user_to_add:
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
        # Check if the user is already in the group
        existing_member = GroupMember.query.filter_by(
            user_id=user_id,
            group_id=group_id
        ).first()
        
        if existing_member:
            return jsonify({'success': False, 'message': 'User is already a member of this group'}), 400
            
        # Add the user to the group
        new_member = GroupMember(
            user_id=user_id,
            group_id=group_id,
            is_admin=False
        )
        
        db.session.add(new_member)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{user_to_add.name} has been added to the group'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Add group member error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/delete_group', methods=['POST'])
@login_required
def delete_group():
    try:
        current_user = get_current_user()
        data = request.get_json()
        group_id = data.get('group_id')
        
        if not group_id:
            return jsonify({'success': False, 'message': 'Missing group ID'}), 400
            
        # Get the group
        group = db.session.get(Group, group_id)
        if not group:
            return jsonify({'success': False, 'message': 'Group not found'}), 404
            
        # Check if the current user is the creator
        if group.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Only the group creator can delete this group'}), 403
            
        # Delete all messages in the group
        Message.query.filter_by(group_id=group_id).delete()
        
        # Delete all group members
        GroupMember.query.filter_by(group_id=group_id).delete()
        
        # Delete the group
        db.session.delete(group)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Group deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete group error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/edit_group_name', methods=['POST'])
@login_required
def edit_group_name():
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        group_id = data.get('group_id')
        new_name = data.get('name', '').strip()
        
        if not group_id or not new_name:
            return jsonify({'success': False, 'message': 'Missing group ID or name'}), 400
            
        # Get the group
        group = db.session.get(Group, group_id)
        if not group:
            return jsonify({'success': False, 'message': 'Group not found'}), 404
        
        # Check if user is a member of the group (no admin check)
        member_info = GroupMember.query.filter_by(
            user_id=current_user.id,
            group_id=group_id
        ).first()
        
        if not member_info:
            return jsonify({'success': False, 'message': 'You are not a member of this group'}), 403
        
        # Update the group name
        group.name = new_name
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Group name updated successfully',
            'name': new_name
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Edit group name error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/get_direct_messages/<int:user_id>', methods=['GET'])
@login_required
def get_direct_messages(user_id):
    try:
        current_user = get_current_user()
        
        # Получаем сообщения как от текущего пользователя к выбранному, так и наоборот
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
            ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
        ).order_by(Message.created_at).all()
        
        messages_list = []
        
        for message in messages:
            sender = db.session.get(User, message.sender_id)
            messages_list.append({
                'id': message.id,
                'sender_id': message.sender_id,
                'sender_name': sender.name,
                'content': message.content,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({
            'success': True,
            'messages': messages_list
        })
        
    except Exception as e:
        print(f"Get direct messages error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/get_group_messages/<int:group_id>', methods=['GET'])
@login_required
def get_group_messages(group_id):
    try:
        current_user = get_current_user()
        
        # Проверяем, является ли пользователь участником группы
        is_member = GroupMember.query.filter_by(
            user_id=current_user.id,
            group_id=group_id
        ).first()
        
        if not is_member:
            return jsonify({'success': False, 'message': 'Вы не являетесь участником этой группы'}), 403
        
        # Получаем все сообщения группы
        messages = Message.query.filter_by(group_id=group_id).order_by(Message.created_at).all()
        
        messages_list = []
        
        for message in messages:
            sender = db.session.get(User, message.sender_id)
            messages_list.append({
                'id': message.id,
                'sender_id': message.sender_id,
                'sender_name': sender.name,
                'content': message.content,
                'created_at': message.created_at.strftime('%Y-%м-%d %H:%M:%S')
            })
        
        return jsonify({
            'success': True,
            'messages': messages_list
        })
        
    except Exception as e:
        print(f"Get group messages error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/delete_direct_chat', methods=['POST'])
@login_required
def delete_direct_chat():
    try:
        current_user = get_current_user()
        data = request.get_json()
        friend_id = data.get('friend_id')
        
        if not friend_id:
            return jsonify({'success': False, 'message': 'Missing friend ID'}), 400
            
        # Delete all messages between the current user and the friend (in both directions)
        Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == friend_id)) |
            ((Message.sender_id == friend_id) & (Message.recipient_id == current_user.id))
        ).delete()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Chat deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete direct chat error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error deleting chat: {str(e)}'}), 500

@app.route('/get_user_groups', methods=['GET'])
@login_required
def get_user_groups():
    try:
        current_user = get_current_user()
        
        # Get groups in which the user is a member
        groups_query = db.session.query(Group).join(GroupMember).filter(
            GroupMember.user_id == current_user.id
        ).all()
        
        groups_list = []
        for group in groups_query:
            # Count members
            member_count = GroupMember.query.filter_by(group_id=group.id).count()
            
            # Check if current user is admin
            user_membership = GroupMember.query.filter_by(
                user_id=current_user.id,
                group_id=group.id
            ).first()
            
            is_admin = user_membership.is_admin if user_membership else False
            
            groups_list.append({
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'avatar': group.avatar,
                'member_count': member_count,
                'is_admin': is_admin,
                'is_creator': (group.creator_id == current_user.id)
            })
        
        return jsonify({
            'success': True,
            'groups': groups_list
        })
        
    except Exception as e:
        print(f"Get user groups error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Обработчики событий WebSocket
@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        current_user = get_current_user()
        emit('status', {'msg': f'{current_user.name} подключился'})

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        current_user = get_current_user()
        emit('status', {'msg': f'{current_user.name} отключился'})

@socketio.on('join')
def handle_join(data):
    room = data['room']
    join_room(room)
    current_user = get_current_user()
    emit('status', {'msg': f'{current_user.name} присоединился к комнате {room}'}, room=room)

@socketio.on('leave')
def handle_leave(data):
    room = data['room']
    leave_room(room)
    current_user = get_current_user()
    emit('status', {'msg': f'{current_user.name} покинул комнату {room}'}, room=room)

@socketio.on('message')
def handle_message(data):
    current_user = get_current_user()
    room = data.get('room')
    message_content = data.get('message')
    recipient_type = data.get('recipient_type', 'user')  # 'user' или 'group'
    
    if not message_content:
        return
    
    # Создаем новое сообщение в БД
    new_message = Message(
        sender_id=current_user.id,
        content=message_content
    )
    
    # Определяем получателя в зависимости от типа
    if recipient_type == 'user':
        recipient_id = data.get('recipient_id')
        new_message.recipient_id = recipient_id
    else:
        group_id = data.get('group_id')
        new_message.group_id = group_id
    
    try:
        db.session.add(new_message)
        db.session.commit()
        
        # Отправляем сообщение в комнату через WebSocket
        emit('new_message', {
            'id': new_message.id,
            'sender_id': current_user.id,
            'sender_name': current_user.name,
            'content': message_content,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }, room=room)
    except Exception as e:
        db.session.rollback()
        print(f"Error sending message: {str(e)}")
        emit('error', {'msg': 'Ошибка при отправке сообщения'})

# Создаем таблицы при запуске
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    socketio.run(app, debug=True)  # Вместо app.run() используем socketio.run()
