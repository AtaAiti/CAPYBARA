from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'  # Обратите внимание на 3 слэша
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Добавьте секретный ключ

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100))
    password = db.Column(db.String(100))

    def __repr__(self):
        return f'<User {self.id}>'

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        user = User(name=name, email=email, password=password)
        try:
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('mainWindow'))#url_for - работает только с функциями, а не с маршрутами
        except:
            return "При добавлении пользователя произошла ошибка"
    else:   
        return render_template("register.html")#render_template - направляет на файл html


@app.route('/mainWindow') #пока так будет
def mainWindow():
    return render_template("mainWindow.html") 


# Создаем таблицы при запуске
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

# from flask import Flask, render_template, url_for

# from flask_sqlalchemy import SQLAlchemy


# app = Flask(__name__)
# # создаем объект Flask с которого будем создавать функционал сервера

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'  
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключаем ненужные уведомления
# db = SQLAlchemy(app)#инициализация базы данных

# class User(db.Model):
#     id = db.Column(db.Integer, primary_key=True)#primary_key - только уникальные айди
#     name = db.Column(db.String(50), nullable=False)#nullable - нельзя установить пустое имя (до 50 символов)
#     email = db.Column(db.String(100))
#     password = db.Column(db.String(100))


#     def __repr__(self):
#         return f'<User {self.id}>' #выдается объект и его айди для возвращения записи из базы данных
    


# @app.route('/home')
# @app.route('/')
# def index():
#     return "Hello World"
# # можно вести разные маршруты к одной функции 

# @app.route('/about')
# def about():
#     return "About page"


# @app.route('/user/<string:name>/<int:id>')
# def user(name, id):
#     return "User page: " + name + ' - ' + str(id)
# # возвращаем только строку, поэтому преобразуем айди в строку


# @app.route('/index')
# def firstPage():
#     return render_template('index.html')
# #при переходе на /index будет показываться html файл index.html


# if __name__ == "__main__":
#     app.run(debug=True)
# # debug=True - выводятся ошибки для разработчиков, при выпуске продукта меняем на False для пользователей
# # С этого места запускается сервер