# Flask Blog Application

Flask ile geliştirilmiş, MySQL kullanan basit ve production-ready bir blog uygulamasıdır.  
Kullanıcı işlemleri, blog yazıları ve iletişim formu içerir. Veritabanı ve mail bilgileri
environment variable üzerinden yönetilir.

## Mimari
Uygulama Flask route → iş mantığı → MySQL → Jinja2 template akışıyla çalışır.
Geliştirme ve canlı ortam ayarları ayrıdır, hassas bilgiler koda gömülmez.

![Architecture](screenshots/flaskblog.png)

## Gereksinimler
Python 3.x  
Flask  
MySQL  

## Kurulum
Repoyu klonla:
git clone https://github.com/kullaniciadi/flask-blog.git
cd flask-blog

Virtual environment:
python3 -m venv venv
source venv/bin/activate

Paketleri yükle:
pip install -r requirements.txt

Veritabanı oluştur:
MySQL üzerinde boş bir veritabanı oluştur ve adını aşağıdaki değişkende kullan.

Environment variable’ları ayarla:
SECRET_KEY=your_secret_key
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=******
MYSQL_DB=blog
MYSQL_PORT=3306
MAIL_FROM=
MAIL_TO=
MAIL_USER=
MAIL_PASSWORD=

Çalıştır:
flask run

## Not
Production ortamda DEBUG=False kullanılmalıdır.
Gizli bilgiler GitHub’a eklenmez.
