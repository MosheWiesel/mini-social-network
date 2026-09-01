# פריסת הפרויקט ב־Railway וב־MongoDB Atlas

הארכיטקטורה לאחר הפריסה:

```text
GitHub
   ↓
Railway — Flask + Gunicorn + הקבצים הסטטיים
   ├── /data/app.db על Railway Volume
   └── MongoDB Atlas דרך MONGO_URI
```

## 1. העלאת הקוד ל־GitHub

1. צרו repository חדש ב־GitHub.
2. העלו אליו את כל קובצי הפרויקט מלבד קבצים שמופיעים ב־`.gitignore`.
3. ודאו במיוחד ש־`.env`, הקובץ `app.db` ותיקיית `.venv` לא הועלו.

אין להכניס סיסמת Atlas או connection string אמיתי לקוד או ל־`.env.example`.

## 2. יצירת MongoDB Atlas

1. היכנסו ל־[MongoDB Atlas](https://www.mongodb.com/atlas/database) וצרו Project.
2. צרו Cluster במסלול החינמי הזמין בחשבון.
3. במסך **Database Access** צרו Database User ייעודי לאפליקציה ושמרו את שם המשתמש והסיסמה במקום בטוח. זה אינו אותו משתמש שמשמש לכניסה לאתר Atlas.
4. במסך ה־Cluster לחצו **Connect → Drivers**, בחרו Python והעתיקו את כתובת ה־SRV שמתחילה ב־`mongodb+srv://`.
5. החליפו בכתובת את `<username>` ואת `<password>` בפרטי ה־Database User. אם הסיסמה מכילה תווים מיוחדים, יש לבצע להם URL encoding.
6. במסך **Network Access** הוסיפו כתובת שממנה Railway רשאי להתחבר. לדמו קטן ופשוט ניתן זמנית להשתמש ב־`0.0.0.0/0` (**Allow Access from Anywhere**), מפני שכתובת היציאה של השירות עשויה להשתנות. אפשרות זו רחבה ופחות בטוחה; השתמשו בסיסמת מסד חזקה והסירו את ההרשאה כשהדמו מסתיים.

Atlas דורש גם Database User וגם IP Access List לפני שיישום חיצוני יכול להתחבר. ראו [הוראות החיבור הרשמיות של Atlas](https://www.mongodb.com/docs/atlas/connect-to-database-deployment/).

## 3. יצירת שירות Railway מ־GitHub

1. היכנסו ל־[Railway](https://railway.com/) ובחרו **New Project**.
2. בחרו **Deploy from GitHub repo** וחברו את ה־repository.
3. פתחו את השירות שנוצר ובחרו **Variables**.
4. הוסיפו:

   ```text
   MONGO_URI=mongodb+srv://USERNAME:PASSWORD@CLUSTER.mongodb.net/?retryWrites=true&w=majority
   SQLITE_PATH=/data/app.db
   ```

   אין צורך להגדיר `PORT`; Railway מספק אותו לשירות בזמן הריצה.

## 4. הוספת Volume קבוע ל־SQLite

1. ב־Railway צרו Volume וחברו אותו לשירות ה־Flask.
2. הגדירו את **Mount Path** לערך המדויק:

   ```text
   /data
   ```

3. ודאו שהמשתנה `SQLITE_PATH` הוא `/data/app.db`.

ה־Volume זמין בזמן הריצה, ולכן אתחול מסד הנתונים נמצא בפקודת ההפעלה ולא ב־pre-deploy command. ראו [Railway Volumes](https://docs.railway.com/volumes).

## 5. פקודת ההפעלה

ב־Railway, תחת **Settings → Deploy → Custom Start Command**, הגדירו בדיוק:

```bash
python initial_script.py && gunicorn app:app --bind 0.0.0.0:$PORT
```

`initial_script.py` רק יוצר טבלאות או collection חסרים ואינו מוחק נתונים. אין להריץ את `seed_data.py` ב־Railway.

## 6. פריסה וכתובת ציבורית

1. לחצו **Deploy** ובדקו ב־Deploy Logs שהאתחול הצליח וש־Gunicorn מאזין לפורט שסופק.
2. עברו אל **Settings → Networking → Public Networking**.
3. לחצו **Generate Domain**. Railway ייצור כתובת HTTPS ציבורית. ראו [Public Networking](https://docs.railway.com/networking/public-networking).
4. פתחו את הכתובת ללא נתיב נוסף. הנתיב `/` מציג את `static/index.html`.

## 7. בדיקת דמו מרובה משתמשים

1. פתחו את כתובת Railway בדפדפן רגיל ובחלון Incognito או בדפדפן נוסף.
2. הירשמו עם שני שמות משתמש שונים.
3. שלחו בקשת חברות ממשתמש א' למשתמש ב'.
4. אצל משתמש ב' פתחו **בקשות** ואשרו את הבקשה.
5. צרו פוסט מכל משתמש, רעננו את הפיד ובדקו שהפוסט העצמי ופוסט החבר מופיעים.
6. בדקו תגובה, תשובה לתגובה, דחיית בקשה ומחיקת פוסט עצמי.

## פתרון תקלות קצר

- `ServerSelectionTimeoutError`: בדקו את `MONGO_URI`, את סיסמת Database User ואת Atlas Network Access.
- `unable to open database file`: ודאו שה־Volume מחובר ב־`/data` וש־`SQLITE_PATH=/data/app.db`.
- `gunicorn: command not found`: ודאו ש־`requirements.txt` נמצא בשורש ה־repository ושה־build הושלם.
- האתר אינו ציבורי: צרו domain תחת Public Networking.
- שינוי משתנים ב־Railway נכנס לתוקף רק אחרי Deploy של השינויים הממתינים. ראו [Railway Variables](https://docs.railway.com/variables).

## Demo Security Limitations

זהו פרויקט סטודנט להדגמה, לא מערכת production מאובטחת:

- סיסמאות משתמשי האפליקציה נשמרות כרגע כטקסט גלוי ב־SQLite.
- השרת סומך על כותרת `User-Id` שנשלחת מהדפדפן ואין session או token מאומת.
- כל מי שמקבל את הכתובת הציבורית יכול להירשם ולנסות את ה־API.
- SQLite מתאים לדמו קטן עם מופע Railway יחיד; אין להריץ מספר replicas שכותבים לאותו קובץ.
- `0.0.0.0/0` ב־Atlas Network Access מתאים רק לדמו זמני ומרחיב את שטח החשיפה.

לפני שימוש אמיתי יש להוסיף hashing לסיסמאות, אימות session/token, הרשאות שרת קשיחות והגבלת גישה למסדי הנתונים.
