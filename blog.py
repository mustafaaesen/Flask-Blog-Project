from flask import Flask,render_template,flash,redirect,url_for,session,logging,request,jsonify
from flask_mysqldb import MySQL
from wtforms import Form,StringField,TextAreaField,PasswordField,validators,SelectField
from passlib.hash import sha256_crypt
from functools import wraps
from werkzeug.utils import secure_filename
from flask_wtf import CSRFProtect

import smtplib
from email.mime.multipart import MIMEMultipart# mesaj göbdesii için
from email.mime.text import MIMEText#mesaj göbdesi içerği için
import sys# ekrandaki hata mesajları
from flask_limiter import Limiter#limitler için
from flask_limiter.util import get_remote_address

import re
import math


import os

app= Flask(__name__) # flask nesnesi türetme uygulama oluşturma

app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD")
app.config["MYSQL_DB"] = os.environ.get("MYSQL_DB")
app.config["MYSQL_PORT"] = int(os.environ.get("MYSQL_PORT", 3306))
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
app.config["MYSQL_CHARSET"] = "utf8mb4"

app.config["UPLOAD_FOLDER"]="static/uploads/profile_pics"
app.config["ARTICLE_IMAGE_FOLDER"]="static/uploads/article_images"


app.secret_key = os.environ.get("SECRET_KEY")
csrf = CSRFProtect(app)
mysql=MySQL(app)# nesne türetilerek uygulmaya bağlantıyı tamamlama

limiter = Limiter(
    get_remote_address,       # Kullanıcının IP adresine göre sınır koyar
    app=app,
    default_limits=["100 per hour"],  # Global sınır: 1 saatte 100 istek
    storage_uri="memory://",   # Küçük projeler için yeterli, Redis gibi harici sistem de kullanılabilir
)



#Kullanıcı Giriş Kontrolü Decoratorı
#Login route unu kontrol eder eğer kullanıcı giriş yapatıysa çalıştırır
#yapmadıysa çalıştırmaz böylelikle taryıcıdan / ile erişimin önüne geçilmiş olur
def login_required(f):
    @wraps(f)

    def decorated_function(*args,**kwargs):

        if "logged_in" in session:#dahboardda logged in session varsa giriş yapılmıştır

            return f(*args,**kwargs)
        else:#yoksa giriş yapmamıştır flash mesajı verilir
            flash("Bu Sayafayı Görüntüleyebilmek İçin Lütfen Giriş Yapın!!!","danger")
            return redirect(url_for("login"))

    return decorated_function


#Kullanıcı Kaydı oluşturma formu WTForms ile
class RegisterForm(Form):
    name=StringField("İsim Soyisim", validators=[validators.length(min=3, max=30),validators.DataRequired()])
    job=StringField("İş Tanımı",validators=[validators.length(min=5,max=100),validators.DataRequired()])
    username=StringField("Kullanıcı Adı",validators=[validators.length(min=5,max=35)])
    email=StringField("E-Posta Adresi",validators=[validators.Email(message="Lütfen Geçerli Bir E-Mail Adresi Giriniz")])
    password=PasswordField("Parola",validators=[
        validators.DataRequired(message="Lütfen Bir Parola Belirleyin"),
        validators.EqualTo(fieldname="confirm",message="Girilen Parolalar Aynı Değil!"),#iki parolanın eşleşemsini kontrol eder

    ])
    confirm=PasswordField("Parolanızı Doğrulayın")

class LoginForm(Form): #kullanıcı adı ve parola alınacağı form
    username=StringField("Kullanıcı Adınızı Giriniz")
    password=PasswordField("Parola")

#Makale Formu

class ArticleForm(Form):
    #Makale Başlığı ve İçeriği İçin alanlar
    #diğer bilgileri sessionlardan bağlantılı olarak alacağız

    title=StringField("Makale Başlığı", validators=[validators.Length(min=5,max=100)])
    interest_area=StringField("Makalenin İlgi Alanı",validators=[validators.length(min=5,max=100)])
    content=TextAreaField("Makale İçeriği",validators=[validators.Length(min=10)])
    
    

class UserUpdateForm(Form):
    name=StringField("İsim Soyisim", validators=[validators.length(min=3, max=30),validators.DataRequired()])
    job=StringField("İş Tanımı",validators=[validators.length(min=5,max=100),validators.DataRequired()])
    username=StringField("Kullanıcı Adı",validators=[validators.length(min=5,max=35)])
    email=StringField("E-Posta Adresi",validators=[validators.Email(message="Lütfen Geçerli Bir E-Mail Adresi Giriniz")])
    
    
class CommentForm(Form):
    comment=TextAreaField("Yorumunuz",validators=[validators.length(min=50,max=500),validators.DataRequired()])

class ContactForm(Form):
    name=StringField("Ad Soyad",validators=[validators.length(min=6,max=50),validators.DataRequired()])
    email=StringField("E-Posta Adresi",validators=[validators.Email("Lütfen geçerli bir e-posta adresi giriniz",validators.DataRequired())])
    phone=StringField("Telefon",validators=[validators.DataRequired(),validators.length(min=10,max=15)])
    service=SelectField("Hizmet",choices=[
        ('support','Destek'),
        ('offer','Teklif'),
        ('feedback', 'Geri Bildirim')
        
    ],validators=[validators.DataRequired()])
    message=TextAreaField("Mesaj",validators=[validators.length(min=20),validators.DataRequired()])

#Hata mesajları dinamik
#hataları yakarl ve error html tarafını hataya göre dinamik şekilde günceller
@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(408)
@app.errorhandler(404)
@app.errorhandler(429)
@app.errorhandler(500)
@app.errorhandler(502)
@app.errorhandler(503)
@app.errorhandler(504)

def handlererro(e):
    
    code=getattr(e,'code',500)#hata kodunu alma
    
    messages={
        
        400:{
            
            "title":"Oops! Geçersiz İstek",
            "description":"Sunucu,isteğinizi anlayamadı.Lütfen form veya veri girişinizi kontrol edin"
            
        },
        
        401:{
            
            "title":"Oops! Yetkilendirme Gerekli",
            "description":"Bu sayfaya erişmek iin giriş yapmanız gerekiyor"
            
        },
        
        403:{
            
            "title":"Oops! Erişim Engellendi",
            "description":"Bu işlemi yapmanız için gerekli izniniz yok"
            
        },
        
        
        404:{
            "title":"Oops! Sayfa Bulunamadı",
            "description":"Aradığınız sayfa taşınmış,silinmiş veya hiç varolmamış olabilir."
        },
        
        405:{
          
          "title":"Oops! Geçersiz İstek Yöntimi",
          "description":"Bu URL için kullandığınız HTTP yöntemi desteklenmiyor"
            
        },
        
        408:{
          
          "title":"Oops! İstek Zaman Aşımına Uğradı",
          "description":"Sunucu isteğinizi zamanında alamadı.Lütfen daha sonra tekrar deneyiniz"
            
        },
        
        
        429:{
            "title":"Oops! Çok Fazla İstek Gönderildi.",
            "description":"Kısa sürede çok fazla işlem yaptınız.Lütfen birkaç dakika bekleyip tekrar deneyin"
        },
        500:{
            "title":"Oops! Sunucu Hatası",
            "description":"Beklenmeyen bir hata oluştu.Geliştirici ekibi bilgilendirildi."
        },
        
        502:{
            
            "title":"Oops! Geçersiz Sunucu Yanıtı",
            "description":"Sunucu geçersiz bir yanıt döndürdü.Lütfen tekrar deneyin"
        },
        
        503:{
            
            "title":"Oops ! Sunucu Kullanılamıyor",
            "description":"Suncuu şu anda geçici olarak kullanılamıyor. Lütfen daha sonra tekrar deneyin"
        },
        
        504:{
            
            "title":"Oops! Ağ Geçidi Zaman Aşımı",
            "description":"Sunucular arasında bağlantı zaman aşımına uğradı. Lütfen daha sonra tekrar denyin."
        }
    }
    #eğer bilinmeyen bir hata alınmışsa kod gönderilir
    message=messages.get(code,{
        "title":"Oops! Bilinmeyen Hata",
        "description":"Bilinmeyen bir hata meydana geldi.Lütfen daha sonra tekrar deneyin"
    })
    
    return render_template("errors.html",code=code, title=message["title"],description=message["description"]),code


@app.route("/")
def index():
    
    cursor=mysql.connection.cursor()
    sorgu="""  
    
        SELECT 
            a.id,
            a.title,
            a.interest_area,
            a.author,
            a.content,
            a.created_date,
            a.article_image,
            COUNT(c.id) as comment_count
            FROM articles a
            LEFT JOIN comments c ON c.article_id=a.id
            GROUP BY a.id
            ORDER BY a.created_date DESC
            LIMIT 5
            
    
        """
        
    cursor.execute(sorgu)
    articles=cursor.fetchall()
    
    for article in articles:#okuma sürelerini hesaplama
        word_count=len(article['content'].split())#kelime sayısı hesaplama
        article['reading_time']=math.ceil(word_count/200)#okuma süresi dk
        article['created_date'] = article['created_date'].strftime("%d.%m.%Y") 
           
    return render_template("index.html", articles=articles)

@app.route("/about")
def about():

    return render_template("about.html")




#kayıt oma register sayfası

@app.route("/register",methods=["GET","POST"])
@limiter.limit("5 per minute")
def register():
      
    form=RegisterForm(request.form)

    if request.method=="POST" and form.validate():

        #from bilgileri doluysa alınır.
        name=form.name.data
        job=form.job.data
        username=form.username.data
        email=form.email.data
        password=sha256_crypt.encrypt(form.password.data)#parola şifrelenmiş şekilde veritabanına kaydedilecek

        #veritabanında işlem yapabilmek için mysqlden cursor oluşturulmalı
        
        #profil fotoğrafı için dosya kontrolü
        if "profile_photo" in request.files:
            file=request.files["profile_photo"]
            if file and file.filename!="":
                filename=secure_filename(file.filename)#dosya adını alma
                file.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))
                #dosyaya fotoğrafı akydetme
                
            else:
                #aksi durumda profil fotoğrafı yoktur default gelir
                filename="default.jpg"
        else:
            filename="default.jpg"
            
                
        
        cursor=mysql.connection.cursor()#cursor oluşturuldu

        sorgu="INSERT INTO users(name,job,email,username,password,profile_pic) VALUES(%s,%s,%s,%s,%s,%s)"
        #kayıt sorgusu tanımlandı bununla değerler parametre olarak verildi

        cursor.execute(sorgu,(name,job,email,username,password,filename))#demet şeklinde değerler verildi
        #tek değer olsa sadece , verilirdi demet şeklinde olması için sonuna
        mysql.connection.commit()#sorguda değişiklik varsa kaydedilmesi için commit gereklidir.
        cursor.close()#flash mesajlarını gisterebiliriz

        flash("Kayıt Başarılı...","success")
          

        return redirect(url_for("login"))
    else:
        return render_template("register.html",form=form)

#Login işlemleri

@app.route("/login",methods=["GET","POST"])
@limiter.limit("5 per minute")
def login():

    form=LoginForm(request.form)

    if request.method=="POST": #kullanıcı giriş seçeneğine tıkladıysa
        #bilgiler formdan alınır veritabanında kontrol edilir
        #varsa giriş yapar yoksa hatalı mesajı verir

        username=form.username.data
        password_entered=form.password.data

        #bilgilerin sorgulanacğı cursor tanımı

        cursor=mysql.connection.cursor()

        #kontrol edilecek sorgu

        sorgu="Select * from users where username = %s"# kullanıcı adını veri tabanında arama

        result=cursor.execute(sorgu,(username,))
        #sorgu dmet şeklinde veriilip çalıştırılıp sonucu result değişkenine atanır
        #bu değişken 0 ise sonuç yoktur hatalı mesajı verilir değilse giriş yapılma işlemleri yapılır

        if result>0:
            #result değeri 0 dan büyükse kullanıcı adı bulunmuştur
            #duruma göre parola kontrolü yapılıp ilgili yönlendirmeler verilir

            data=cursor.fetchone()#veritabanından kullanıcı bilgileri alınır

            real_password=data["password"]#kulalnıcının gerçek şifresi sözlğk gibi alınır

            if sha256_crypt.verify(password_entered,real_password):
                # sha25 nın verify fonksiyonu ile şifreler karşılaştırlır
                #doğruysa giriş yapılır yanlışsa uyarıverilir
                flash("Parola Doğru! Giriş Başarılı...","success")

                session["logged_in"]=True
                session["username"]=username
                session["id"] = data["id"]


                return redirect(url_for("index"))
            else:
                #aksi durumda parola hatlaıdır tekrar girmesi istenir
                flash("Parola Hatalı! Tekrar Deneyiniz...","danger")
                return redirect(url_for("login"))
                        
        else:
            #büyük değilse kullanıcı adı yanlıştır flash mesaj ile yeniden girmeye yönelndirilir
            flash("Kullanıcı Adı Hatalı... Tekrar Deneyiniz...","danger")

            return redirect(url_for("login"))

    return render_template("login.html",form=form)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))



@app.route("/dashboard")
@login_required#tanımlanan kotnrol decoratorını kullanma çalışmadan hemen önce ona gider
#session kontrolü sonucuna göre kulalnıcı yönlendirilir
def dashboard():
    article_count=0
    cursor=mysql.connection.cursor()
    page=request.args.get('page',1,type=int)
    per_page=4
    sorgu_total="Select count(*) from articles where author=%s"
    cursor.execute(sorgu_total,(session["username"],))
    total = list(cursor.fetchone().values())[0]
    offset=(page-1)*per_page
    
    sorgu_user="Select * from users where username=%s"
    cursor.execute(sorgu_user,(session["username"],))
    user=cursor.fetchone()
    
    
    sorgu="Select * from articles where author= %s LIMIT %s OFFSET %s"#kullanıcının adına göre makaleleri almak için

    result=cursor.execute(sorgu,(session["username"],per_page,offset))#sessionlardan kullanıcı adını alma ve demet olarak gönderme

    if result>0:#kullanıcnın makalesi varsa
        articles=cursor.fetchall()
        
        article_count=total
        total_pages = (total + per_page - 1) // per_page #toplam sayfa sayısını hesaplama

        return render_template("dashboard.html", user=user ,articles=articles,article_count=article_count,page=page,total_pages=total_pages)#makalesi varsa dashboarda gönderilir
    else:#makale yoksa doğrudan sayfaya gönderme
         
        return render_template("dashboard.html",user=user,article_count=article_count,page=1,total_pages=1)



#Makale Ekleme

@app.route("/addarticle",methods=["GET","POST"])
@login_required
def addarticle():

    form=ArticleForm(request.form)

    if request.method=="POST" and form.validate():#makale yazılıp kaydedilecekse doğru mu kontrolü

        title=form.title.data#bilgilerin alınması
        interest_area=form.interest_area.data
        content=form.content.data
        
        if "article_image" in request.files:
            file=request.files["article_image"]
            if file.filename!="":
                filename=secure_filename(file.filename)
                file.save(os.path.join(app.config["ARTICLE_IMAGE_FOLDER"],filename))
                
            else:
                filename="default_article.jpg"
        else:
            filename="defaul_article.jpg"

        cursor=mysql.connection.cursor()

        sorgu="Insert into articles (title,interest_area,author,content,article_image) VALUES(%s, %s,%s, %s,%s)"

        cursor.execute(sorgu,(title,interest_area,session["username"],content,filename))

        mysql.connection.commit()#veritabnında yapılan değişikliklerin kaybedilmemeis için,

        cursor.close()
        flash("Makale Kaydı Başarılı!!!","success")
        return redirect(url_for("dashboard"))



    return render_template("addarticle.html",form=form)

#Makale Sayfası

@app.route("/articles")
def articles():
    
    cursor=mysql.connection.cursor()
    
    page=request.args.get('page',1,type=int)#url den alınan sayfa numarası
    per_page=6#sayfa başı makale sayısı
    
    cursor.execute("Select count(*) from articles")#toplam makale sayısı sorgusu
    total = list(cursor.fetchone().values())[0]
    
    offset=(page-1)*per_page
    
    sorgu="""
        SELECT articles.*, users.profile_pic,users.job
        FROM articles
        INNER JOIN users ON articles.author = users.username
        ORDER BY articles.created_date DESC
        LIMIT %s OFFSET %s 
    """#makaleleri veritabanından çekme  #sorgu offsetle daraltıldı sayfa başına çalışacak

    cursor.execute(sorgu,(per_page,offset))
    result=cursor.rowcount # kaç kayıt geldiğini atırlama

    if result>0: #veritabanında makale varsa

        articles=cursor.fetchall()
        cursor.execute( # artık ilgili sayfadaki makaleler görüneceği için ekstra recetn post oluşturulur gönderilir
            """
            SELECT articles.* , users.profile_pic,users.job
            FROM articles
            INNER JOIN users ON articles.author= users.username
            ORDER BY articles.created_date DESC
            LIMIT 5
            """
        )
        #ilgili makaleler son 5 makale sayfa sayısı ve sayfa gönderilir
        recent_posts=cursor.fetchall()
        total_pages = (total + per_page - 1) // per_page #toplam sayfa sayısını hesaplama
            
        return render_template("articles.html",articles=articles,recent_posts=recent_posts,page=page,total_pages=total_pages)#articles html içerisinde for döngüsü ile
         #gösterebilmek için gönderildi
    else:# result 0 dır makale yoktur
        #articles html de makale yok sayfaya gönderilmez

        return render_template("articles.html",page=1,total_pages=1)

#Detay Sayfası 

@app.route("/article/<string:id>")
def article(id): # makalelere tıklnadığında id elerine göre yeni linkte açılması için dinamik tasarlanan 
    #sayfa

    cursor = mysql.connection.cursor()

    sorgu="""
    
      SELECT articles.*,users.profile_pic,users.job
      FROM articles
      INNER JOIN users ON articles.author=users.username
      WHERE articles.id=%s
    
    """

    result=cursor.execute(sorgu,(id,))
    
    
     
    if result>0:
        
        #ayni idli makaladen birden fazla olamayacğına göre id ye göre bakıyoruz

        article=cursor.fetchone()
        text_only = re.sub('<[^<]+?>', '', article["content"])  # etiketleri çıkar
        word_count = len(text_only.split())
        read_time = math.ceil(word_count / 200) 
        
        #yorum tablsoundan yorumları ve yorum yapan kişinin bilgileirini inner join ile çekme
        #varsa makalenin yorumlarını dönecek forma formda ise parent id değerine göre ana yoeum veya yanıt yorumu olduğu anlaşılır
        sorgu_comments="""
            SELECT
                c.id,
                c.article_id,
                c.user_id,
                c.parent_id,
                c.content,
                c.created_date,
                u.username,
                u.profile_pic
            FROM comments c
            INNER JOIN users u ON c.user_id=u.id
            WHERE c.article_id=%s
            ORDER BY c.created_date  ASC
        
        
        """
        cursor.execute(sorgu_comments,(id,))#id ve sorguyu çalıştırma
        comments=cursor.fetchall()
        comment_count=len(comments)
        
        
        sorgu2="""
        SELECT id, title, article_image, created_date 
        FROM articles 
        ORDER BY created_date DESC 
        LIMIT 5

        
        """
        cursor.execute(sorgu2)
        recent_posts=cursor.fetchall()

        return render_template("article.html",article=article,comments=comments,comment_count=comment_count,recent_posts=recent_posts,read_time=read_time)

    else:
        # herhangi bir  makale olmamamsı durumudur.

        return render_template("article.html")#doğrudan html döndürülür


#Makale Silme

@app.route("/delete/<string:id>")
@login_required
def delete(id):
    #üste tanımlanmış olan giriş kontrolü yapan decoratoru kullnarak
    #giriş yapmadan silmeyi önlersin

    cursor=mysql.connection.cursor()
    sorgu="Select * from articles where author=%s and id=%s"# id ve yazara göre makaleyi arama
    #makale var mı yazar var mı ve ikisi ilişkili mi

    result=cursor.execute(sorgu,(session["username"],id))

    if result>0:
        sorgu2="Delete from articles where id=%s"# eğer doğruysa gelen id ye göre silme

        cursor.execute(sorgu2,(id,))#veritabanı değişte  commti yapılır
        mysql.connection.commit()

        return redirect(url_for("dashboard"))

    else:#makale ait değilse

        flash("Böyle bir makale yok veya bu işleme yetkiniz yok!!!","danger")

        return redirect(url_for("index"))

#Makele Güncelleme

@app.route("/editprofile/<string:id>",methods=["GET","POST"])
@login_required#güncelleme yapabilmesi giriş yapmış olması gereklidir
def editprofile(id):
    
    if request.method=="GET": #gelen metod get ise güncelleme yeri açılır
        #ve kullanıcının karşısına form bilgileri dolu şekilde gösterilir
        
        cursor=mysql.connection.cursor()
        sorgu="Select * from users where id=%s"
        result=cursor.execute(sorgu,(id,))
        
        if result==0:#kullanıcı prfili bulunmadıysa
            flash("Profil Bulunamadı!!!...","danger")
            
            return redirect(url_for("index"))
        else:
            
            user=cursor.fetchone()#kulalnıcı bilgilerini alma
            form=UserUpdateForm()#kulalnıcı güncelleme formunu oluşturma
            form.name.data=user["name"]
            form.job.data=user["job"]
            form.username.data=user["username"]
            form.email.data=user["email"]
            
            return render_template("updateuser.html",form=form)

    else:#kullanıcı formu kaydettiyse POST request gelmiştir bilgierlin kaydeilmesi gerekir
        
        
        
        cursor=mysql.connection.cursor()
        sorgu="Select * from users where id=%s"
        result=cursor.execute(sorgu,(id,))
        user = cursor.fetchone()
        form=UserUpdateForm(request.form)#formdan bilgilerin alınması
        newName=form.name.data
        newJob=form.job.data
        newUsername=form.username.data
        newEmail=form.email.data
        
        if "profile_photo" in request.files:
            file=request.files["profile_photo"]
            if file and file.filename!="":
                filename=secure_filename(file.filename)
                filepath=os.path.join(app.config["UPLOAD_FOLDER"],filename)
                file.save(filepath)
                
                old_pic = user["profile_pic"] #eski fotoğrafı silme
                if old_pic != "default.jpg":
                    old_path=os.path.join(app.config["UPLOAD_FOLDER"],old_pic)
                    #eski dosyayı bulma
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    
                    
                
            else:
                filename=user["profile_pic"]#eski fotoğrafı koruma
                
        else:
            filename=user["profile_pic"]
        
        session["username"]=newUsername    
        
        sorgu2="Update users set name=%s,job=%s,username=%s,email=%s,profile_pic=%s where id=%s"
        
        cursor=mysql.connection.cursor()
        cursor.execute(sorgu2,(newName,newJob,newUsername,newEmail,filename,id))
        mysql.connection.commit()
        flash("Profil Güncelleme Başarılı...","success")
        return redirect(url_for("dashboard"))

@app.route("/edit/<string:id>",methods=["GET","POST"])#makaleyi dinamik url ile get post metodudları var o şekilde güncelleme yapabiliriz
@login_required#güncelleme yapabilmesi için giriş yapmış olması gerekmekte
def edit(id):

    if request.method=="GET": #method get ise güncelleme yapılır
        cursor=mysql.connection.cursor()
        #sorgu komutunun cevabıa göre 4 durum var
        #1Makale Olmama durumu
        #2 Makalenin olup kullanıcıynın olmamması durumu
        #Makale olması durumu
        #Makale var ama kullanıcınıya ait değil

        sorgu="Select * from articles where id=%s and author=%s"
        result=cursor.execute(sorgu,(id,session["username"]))
        article=cursor.fetchone()

        if result==0: #Makale bulunamama veya kullanıcıya ait olmama durumu id ve yazarı aynı anda verdik
            flash("Böyle bir makale yok veya bu işleme yetkiniz yok!!!","danger")
            return redirect(url_for("index"))
            
        else:#makale var
            
           

            form=ArticleForm()#makale bilgilerinin doldurulacağı form alanı request forma gerek yok 

            form.title.data=article["title"]
            form.interest_area.data=article["interest_area"]
            form.content.data=article["content"]#form bilgilerinin veritabanından çekilenlerle doldurulması

            return render_template("update.html",form=form)# bilgileri html sayfasına geçmek
        


    else:#POST request kısmı kullanıcı değişiklik yapıp güncelle butonuna bastıysa çalışır

        #form tekrardan oluşturulup bilgiler veritabnına atılır

        form = ArticleForm(request.form)

        newTitle=form.title.data
        newInterest=form.interest_area.data
        newContent=form.content.data#yeni bilgilerin alınması
        cursor = mysql.connection.cursor()

        sorgu="Select * from articles where id=%s and author=%s"
        result=cursor.execute(sorgu,(id,session["username"]))
        article=cursor.fetchone()
        
        if "article_image" in request.files:
            file=request.files["article_image"]
            if file and file.filename!="":
                filename=secure_filename(file.filename)
                file_path=os.path.join(app.config["ARTICLE_IMAGE_FOLDER"],filename)
                file.save(file_path)
                old_pic=article["article_image"]
                if old_pic!="default_article.jpg":
                    old_path=os.path.join(app.config["ARTICLE_IMAGE_FOLDER"],old_pic)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                else:
                    filename=article["article_image"]
            
            else:
                filename=article["article_image"]
                    
                
                

        sorgu2="Update articles Set title=%s,interest_area=%s, content=%s,article_image=%s where id=%s"
        # güncelleme komutu idsine göre başlık ve içerik güncelleme
        cursor=mysql.connection.cursor()
        cursor.execute(sorgu2,(newTitle,newInterest,newContent,filename,id))
        #bilgi güncellendi commit yap

        mysql.connection.commit()
        flash("Makale Güncelleme Başarılı","success")
        return redirect(url_for("dashboard"))
#Makale Arama

@app.route("/search",methods=["GET","POST"])
def search():
    #bu sayafaya hem get hem post gelebilir ama sadece post ta görünmesi gerekli
    #Yani butona tıklamadan gösterilmemeli tarayıcı aramasında da çıkabilir bunu önlemek için
    if request.method=="GET":
        return redirect(url_for("index"))
    else:
        keyword=request.form.get("keyword")# arama çubuğundaki yazılan değeri alma

        cursor=mysql.connection.cursor()
        sorgu="Select * from articles where title like '%" + keyword + "%'"
        #like operatörü ile içinde geçen her makaleyi bulma veya benzerlerini

        result=cursor.execute(sorgu)

        if result==0: #makale bulunamaması durumu
            
            flash("Görünüşe Göre Aradığın Tarza Makale Yok:( Hemen Oluştur!)","warning")
            return redirect(url_for("articles"))
        
        else:#makale olması durumu
            articles=cursor.fetchall()#tüm makalelerin alınması

            return render_template("articles.html",articles=articles)


@app.route("/article/<int:article_id>/comment",methods=["POST"])
@login_required
def comment(article_id):
    form=CommentForm(request.form)
   
    if "logged_in" not in session:
        flash("Yorum yapabilmek için giriş yapmalsınız...","warning")
        return redirect(url_for("login"))
    
    #form geçerli ve bilgiler doluysa
    
    if form.validate():
        
        cursor=mysql.connection.cursor()
        content=form.comment.data
        parent_id = request.form.get("parent_id")
        if not parent_id:
            parent_id = None
 
        user_id=session["id"]
        article_id=article_id
        sorgu = "INSERT INTO comments (article_id, user_id, content, parent_id) VALUES (%s, %s, %s, %s)"
        cursor.execute(sorgu, (article_id, user_id, content, parent_id))

        mysql.connection.commit()
        flash("Yorum ekleme başarılı...","success")
        return redirect(url_for("article",id=article_id))
    else:
        flash("Yorum 50-500 Karakter sınırı arasında olmalı!","danger")
        return redirect(url_for("article",id=article_id))


@app.route("/contact",methods=["GET","POST"])
@limiter.limit("2 per minute")
def contact():
    
    form=ContactForm(request.form)
    
    if request.method=="POST" and form.validate():
        
        name=form.name.data
        email=form.email.data
        phone=form.phone.data
        service=form.service.data
        message=form.message.data

        body=f"""
        
        Form Bilgileri
        --------------------------------------------------
        --------------------------------------------------
        Formu Gönderenin:
        Adı:{name}
        
        E-Posta Adresi:{email}
        
        Telefonu:{phone}
        
        Form Servisi:{service}
        
        Mesajı:{message}
        ---------------------------------------------
        """
        MAIL_FROM = os.environ.get("MAIL_FROM")
        MAIL_TO = os.environ.get("MAIL_TO")
        MAIL_USER = os.environ.get("MAIL_USER")
        MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

        msg=MIMEText(body)#mesaj tüeritimi
        msg["Subject"]="Flask Blog'tan Yeni İletişim Formu Gönderisi"
        msg["From"]=MAIL_FROM
        msg["To"]=MAIL_TO
        msg["Reply-To"] = email #kullanıcıya kolay yanıt verebilmek için
        
        try:#Gönderim
            with smtplib.SMTP("smtp.gmail.com",587) as server:
                server.starttls()#protokolün başlaması
                server.login(MAIL_USER,MAIL_PASSWORD)
                #mail gönderecek hesap bilgileri
                server.send_message(msg)#mailin göndeirmi
            
            flash("Tebrikler!Form Gönderimi Başarılı.En Kısa Sürede Görüşmek Üzere...","success")
        
        except Exception as e:
            
            flash(f"Bir Hata Oluştu {e}, Daha sonra tekrar deneyiniz","danger")
        
        return redirect(url_for("contact"))
            
    return render_template("contact.html",form=form)



if __name__ =="__main__": 
    app.run(debug=False) # debug modunu açarak çalıştırma
    #sebebi ise şudur terminaelde çalışınca ana projedir direkt çalıştırılu.
    #başka dosyada modül olarak da kullanılabilir ayrımı için

