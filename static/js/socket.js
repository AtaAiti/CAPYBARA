// Инициализируем socket глобально, до любых обработчиков событий
let socket = io.connect(window.location.protocol + '//' + document.domain + ':' + location.port, {
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

let socketConnected = false;

// Установка обработчиков событий
document.addEventListener('DOMContentLoaded', () => {
    // Обработчик подключения
    socket.on('connect', () => {
        console.log('Connected to WebSocket server');
        socketConnected = true;
        
        // Вызываем пользовательское событие socket-ready
        const event = new Event('socket-ready');
        document.dispatchEvent(event);
    });
    
    // Остальные обработчики...
    socket.on('disconnect', () => {
        console.log('Disconnected from WebSocket server');
        socketConnected = false;
    });
    
    // Обработчик ошибки соединения
    socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        socketConnected = false;
    });
    
    // Обработчик статусных сообщений
    socket.on('status', (data) => {
        console.log('Status message received:', data);
        displayStatusMessage(data.msg);
    });
    
    // Обработчик новых сообщений
    socket.on('new_message', (data) => {
        console.log('New message received:', data);
        displayMessage(data);
    });
    
    // Обработчик ошибок
    socket.on('error', (data) => {
        console.error('Error message received:', data);
        displayErrorMessage(data.msg);
    });
});

// Функция для проверки готовности сокета с поддержкой обещаний (Promise)
function ensureSocketReady() {
    return new Promise((resolve, reject) => {
        if (socket && socketConnected) {
            resolve(socket);
        } else {
            document.addEventListener('socket-ready', () => resolve(socket), { once: true });
            // Таймаут на случай, если сокет не удастся подключить
            setTimeout(() => {
                if (!socketConnected) reject(new Error('Socket connection timeout'));
            }, 5000);
        }
    });
}

// Остальные функции должны использовать ensureSocketReady для гарантии подключения
function joinPrivateRoom(userId, friendId) {
    return ensureSocketReady()
        .then(() => {
            const roomId = `private_${Math.min(userId, friendId)}_${Math.max(userId, friendId)}`;
            console.log(`Joining private room: ${roomId}`);
            
            socket.emit('join', {room: roomId});
            return roomId;
        })
        .catch(error => {
            console.error('Cannot join room:', error);
            return null;
        });
}

// Присоединение к комнате группового чата
function joinGroupRoom(groupId) {
    return ensureSocketReady()
        .then(() => {
            const roomId = `group_${groupId}`;
            console.log(`Joining group room: ${roomId}`);
            
            socket.emit('join', {room: roomId});
            return roomId;
        })
        .catch(error => {
            console.error('Cannot join room:', error);
            return null;
        });
}

// Отправка сообщения
function sendMessage(message, roomId, recipientType, recipientId) {
    return ensureSocketReady()
        .then(() => {
            if (!roomId) {
                throw new Error('Cannot send message: invalid room ID');
            }
            
            const data = {
                message: message,
                room: roomId
            };
            
            if (recipientType === 'user') {
                data.recipient_type = 'user';
                data.recipient_id = recipientId;
            } else {
                data.recipient_type = 'group';
                data.group_id = recipientId;
            }
            
            console.log('Sending message data:', data);
            socket.emit('message', data);
        })
        .catch(error => {
            console.error('Cannot send message:', error);
        });
}

// Функции отображения сообщений на странице
function displayMessage(data) {
    const messagesContainer = document.querySelector('.messages-container');
    const currentUserId = parseInt(document.body.dataset.userId);
    
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    
    // Определяем, является ли сообщение отправленным текущим пользователем
    if (data.sender_id === currentUserId) {
        messageElement.classList.add('sent');
    } else {
        messageElement.classList.add('received');
    }
    
    // Формируем содержимое сообщения
    messageElement.innerHTML = `
        <div class="message-content">${data.content}</div>
        <div class="message-info">
            <span class="message-time">${formatTime(data.timestamp)}</span>
        </div>
    `;
    
    messagesContainer.appendChild(messageElement);
    
    // Прокручиваем контейнер сообщений к последнему сообщению
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function displayStatusMessage(message) {
    const messagesContainer = document.querySelector('.messages-container');
    
    const statusElement = document.createElement('div');
    statusElement.classList.add('status-message');
    statusElement.textContent = message;
    
    messagesContainer.appendChild(statusElement);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function displayErrorMessage(message) {
    // Можно реализовать отображение всплывающего уведомления об ошибке
    alert('Ошибка: ' + message);
}

// Вспомогательная функция для форматирования времени
function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}