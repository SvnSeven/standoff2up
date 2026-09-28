from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from urllib.request import Request,urlopen
import sqlite3,json,random,time

BASE=Path(__file__).resolve().parent
DB=BASE/"upgrader.db"; CACHE=BASE/"catalog_cache.json"
SOURCE="https://standoff-2.com/skins-new.php?command=getModelInfo"
app=FastAPI(title="Standoff 2 Upgrader")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])

def db():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
    c=db();c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT,balance REAL DEFAULT 1000);
    CREATE TABLE IF NOT EXISTS skins(id INTEGER PRIMARY KEY,name TEXT,rarity TEXT,price REAL,image TEXT);
    CREATE TABLE IF NOT EXISTS inv(user_id INTEGER,skin_id INTEGER,qty INTEGER,PRIMARY KEY(user_id,skin_id));
    CREATE TABLE IF NOT EXISTS upgrades(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,a INTEGER,b INTEGER,chance REAL,ok INTEGER,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS opens(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,case_id TEXT,reward_skin INTEGER,reward_gold REAL,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    """)
    demo=[(1,"G22 Pixel Camouflage","Rare",20,"https://placehold.co/160x160/111827/22d3ee?text=G22"),
    (2,"UMP45 Pixel","Rare",35,"https://placehold.co/160x160/111827/22d3ee?text=UMP45"),
    (3,"AKR Sport","Epic",55,"https://placehold.co/160x160/111827/a78bfa?text=AKR"),
    (4,"M4 Lizard","Epic",75,"https://placehold.co/160x160/111827/a78bfa?text=M4"),
    (5,"AWM Genesis","Legendary",90,"https://placehold.co/160x160/111827/f59e0b?text=AWM"),
    (6,"Karambit Gold","Legendary",100,"https://placehold.co/160x160/111827/f59e0b?text=KNIFE")]
    c.executemany("INSERT OR IGNORE INTO skins VALUES(?,?,?,?,?)",demo)
    c.execute("INSERT OR IGNORE INTO users VALUES(1,'DemoPlayer',1000)")
    for x in [(1,1,2),(1,2,1),(1,3,1)]:c.execute("INSERT OR IGNORE INTO inv VALUES(?,?,?)",x)
    c.commit();c.close()
init()

class UReq(BaseModel): user_id:int;from_skin_id:int;to_skin_id:int
class CReq(BaseModel): user_id:int;case_id:str
CASES={
"daily":{"name":"Daily Case","cost":0,"daily":1,"max":100,"r":[(1,42,.10),(1,22,.25),(2,12,.50),(2,8,1),(3,6,5),(4,4,10),(5,3,25),(5,2,50),(6,1,100)]},
"starter":{"name":"Starter Case","cost":25,"daily":0,"max":150,"r":[(1,45,0),(2,30,0),(3,15,0),(4,7,0),(5,3,0)]},
"neon":{"name":"Neon Case","cost":75,"daily":0,"max":300,"r":[(2,35,0),(3,30,0),(4,20,0),(5,10,0),(6,5,0)]},
"premium":{"name":"Premium Case","cost":150,"daily":0,"max":1000,"r":[(3,40,0),(4,30,0),(5,20,0),(6,10,0)]}}

@app.get("/api/state")
def state(user_id:int=1):
    c=db();u=c.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone()
    if not u:c.close();raise HTTPException(404,"User not found")
    inv=c.execute("SELECT s.*,i.qty FROM inv i JOIN skins s ON s.id=i.skin_id WHERE i.user_id=? AND i.qty>0",(user_id,)).fetchall()
    skins=c.execute("SELECT * FROM skins ORDER BY price").fetchall()
    h=c.execute("SELECT u.*,a.name an,b.name bn FROM upgrades u JOIN skins a ON a.id=u.a JOIN skins b ON b.id=u.b WHERE u.user_id=? ORDER BY u.id DESC LIMIT 20",(user_id,)).fetchall()
    c.close();return {"user":dict(u),"inventory":[dict(x) for x in inv],"skins":[dict(x) for x in skins],"history":[dict(x) for x in h]}

@app.post("/api/upgrade")
def upgrade(x:UReq):
    c=db();a=c.execute("SELECT * FROM skins WHERE id=?",(x.from_skin_id,)).fetchone();b=c.execute("SELECT * FROM skins WHERE id=?",(x.to_skin_id,)).fetchone()
    i=c.execute("SELECT qty FROM inv WHERE user_id=? AND skin_id=?",(x.user_id,x.from_skin_id)).fetchone()
    if not a or not b or not i or i["qty"]<1 or b["price"]<=a["price"]:c.close();raise HTTPException(400,"Invalid upgrade")
    ch=min(.95,a["price"]/b["price"]);ok=random.random()<ch
    c.execute("UPDATE inv SET qty=qty-1 WHERE user_id=? AND skin_id=?",(x.user_id,a["id"]))
    if ok:c.execute("INSERT INTO inv VALUES(?,?,1) ON CONFLICT(user_id,skin_id) DO UPDATE SET qty=qty+1",(x.user_id,b["id"]))
    c.execute("INSERT INTO upgrades(user_id,a,b,chance,ok) VALUES(?,?,?,?,?)",(x.user_id,a["id"],b["id"],ch,int(ok)));c.commit();c.close()
    return {"success":ok,"chance":round(ch*100,2),"from":dict(a),"to":dict(b)}

def find(o):
    if isinstance(o,list):
        z=[x for x in o if isinstance(x,dict)]
        if len(z)>2 and any(any(k in x for k in ("name","Name","title","displayName")) for x in z):return z
        for x in o:
            q=find(x)
            if q:return q
    elif isinstance(o,dict):
        for v in o.values():
            q=find(v)
            if q:return q
    return []
def catalog_data(refresh=False):
    if CACHE.exists() and not refresh:
        try:return json.loads(CACHE.read_text())["items"]
        except:pass
    try:
        req=Request(SOURCE,headers={"User-Agent":"SO2-Upgrader/1.0"})
        with urlopen(req,timeout=20) as r:data=json.loads(r.read().decode("utf-8","replace"))
        out=[];seen=set()
        for x in find(data):
            name=x.get("name") or x.get("Name") or x.get("title") or x.get("displayName")
            rid=x.get("id") or x.get("itemId") or x.get("itemDefinitionId")
            if not name:continue
            try:rid=int(rid)
            except:rid=100000000+len(out)
            if rid in seen:continue
            seen.add(rid);raw=(str(name)+" "+str(x.get("type",""))+" "+str(x.get("subtype",""))+" "+str(x.get("category",""))).lower()
            cat="Knives" if any(k in raw for k in ("knife","karambit","butterfly","bayonet","kunai","kukri")) else ("Gloves" if "glove" in raw else ("Stickers" if "sticker" in raw else ("Graffiti" if "graffiti" in raw else "Weapon Skins")))
            out.append({"id":rid,"name":str(name),"display_name":str(name),"type":str(x.get("type","")),"subtype":str(x.get("subtype","")),"rarity":str(x.get("rarity","unknown")),"category":cat,"collection":str(x.get("collection","") or x.get("Collection","")),"image":str(x.get("image","") or x.get("imageUrl","") or x.get("icon","")),"price":None})
        CACHE.write_text(json.dumps({"source":SOURCE,"items":out},ensure_ascii=False));return out
    except:return []
@app.get("/api/catalog")
def catalog(refresh:bool=False):
    items=catalog_data(refresh);cats={}
    for x in items:cats[x["category"]]=cats.get(x["category"],0)+1
    return {"source":SOURCE,"item_count":len(items),"categories":cats,"items":items}

@app.get("/api/cases")
def cases(user_id:int=1):
    c=db();o={}
    for cid,x in CASES.items():
        last=c.execute("SELECT created_at FROM opens WHERE user_id=? AND case_id=? ORDER BY id DESC LIMIT 1",(user_id,cid)).fetchone()
        o[cid]={"id":cid,"name":x["name"],"cost":x["cost"],"daily":x["daily"],"max":x["max"],"last":last["created_at"] if last else None}
    c.close();return {"cases":o}

@app.post("/api/case/open")
def open_case(x:CReq):
    if x.case_id not in CASES:raise HTTPException(404,"Case not found")
    k=CASES[x.case_id];c=db();u=c.execute("SELECT * FROM users WHERE id=?",(x.user_id,)).fetchone()
    if not u:c.close();raise HTTPException(404,"User not found")
    if k["daily"]:
        last=c.execute("SELECT created_at FROM opens WHERE user_id=? AND case_id=? ORDER BY id DESC LIMIT 1",(x.user_id,x.case_id)).fetchone()
        if last:
            sec=c.execute("SELECT (julianday('now')-julianday(?))*86400",(last["created_at"],)).fetchone()[0]
            if sec<86400:c.close();raise HTTPException(429,"Daily Case available once per 24 hours")
    if u["balance"]<k["cost"]:c.close();raise HTTPException(400,"Not enough Gold")
    if k["cost"]:c.execute("UPDATE users SET balance=ROUND(balance-?,2) WHERE id=?",(k["cost"],x.user_id))
    r=random.random()*sum(w for _,w,_ in k["r"]);p=0;pick=k["r"][-1]
    for q in k["r"]:
        p+=q[1]
        if r<=p:pick=q;break
    sid,_,gold=pick;skin=c.execute("SELECT * FROM skins WHERE id=?",(sid,)).fetchone()
    if gold:c.execute("UPDATE users SET balance=ROUND(balance+?,2) WHERE id=?",(gold,x.user_id))
    else:c.execute("INSERT INTO inv VALUES(?,?,1) ON CONFLICT(user_id,skin_id) DO UPDATE SET qty=qty+1",(x.user_id,sid))
    c.execute("INSERT INTO opens(user_id,case_id,reward_skin,reward_gold) VALUES(?,?,?,?)",(x.user_id,x.case_id,sid,gold));c.commit();c.close()
    return {"case_id":x.case_id,"reward":dict(skin),"reward_gold":gold,"max":k["max"]}

@app.get("/health")
def health():return {"ok":True}
