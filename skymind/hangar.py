"""Game-style launcher and interactive USB calibration."""
import math
import importlib.util
import pygame
from . import menu as legacy
from .radio import Radio, Axis

BG=(9,15,24)
INK=(230,242,249)
MUTED=(130,154,176)
TEAL=(64,231,197)

def run():
    pygame.init()
    screen=pygame.display.set_mode((1280,720), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("SKYMIND / Flight deck")
    clock=pygame.time.Clock()
    fonts={s:pygame.font.SysFont("Segoe UI",s,bold=s>=28) for s in (15,18,22,28,42,74)}
    menu=legacy.Menu()
    radio=Radio()
    page="hangar"
    calibration=None
    notice=""
    phase=0
    def text(value,x,y,size=18,color=INK):
        screen.blit(fonts[size].render(value,True,color),(x,y))
    while True:
        buttons=[]
        def button(rect,label,action,active=False):
            r=pygame.Rect(rect)
            hover=r.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen,(32,65,72) if active or hover else (20,32,47),r,border_radius=8)
            pygame.draw.rect(screen,TEAL if active or hover else (43,61,78),r,1,border_radius=8)
            text(label,r.x+18,r.y+13,18,TEAL if active else INK)
            buttons.append((r,action))
        screen.fill(BG)
        phase+=.008
        for x in range(520,1300,60):
            pygame.draw.line(screen,(16,30,43),(x,120),(x-280,720))
        for y in range(180,720,60):
            pygame.draw.line(screen,(16,30,43),(500,y),(1280,y))
        text("S K Y M I N D",40,24,28)
        text("FLIGHT SYSTEM / 02",42,63,15,MUTED)
        text("USB CONNECTÉ" if radio.device else "CLAVIER DISPONIBLE",990,35,15,TEAL)
        pygame.draw.line(screen,(39,59,76),(40,96),(1240,96))
        if page=="hangar":
            text("PRENEZ",64,146,74)
            text("LES COMMANDES.",64,224,74,TEAL)
            text("Votre terrain de vol. Votre radio. Votre trajectoire.",68,324,18,MUTED)
            button((68,390,350,60),"DÉCOLLER  /  Vol libre", "manual_setup",True)
            button((68,466,350,54),"RADIO  /  Connexion et calibration","radio")
            button((68,536,168,54),"Regarder l’IA","play_setup")
            button((250,536,168,54),"Entraîner l’IA","train_setup")
            # Animated vector quadcopter, drawn locally without external assets.
            cx,cy=900,350+int(math.sin(phase)*12)
            for dx,dy in ((-112,-64),(112,-64),(-112,64),(112,64)):
                pygame.draw.line(screen,(61,94,112),(cx,cy),(cx+dx,cy+dy),16)
                pygame.draw.ellipse(screen,TEAL if dy<0 else (106,132,155),(cx+dx-70,cy+dy-26,140,52),2)
                pygame.draw.ellipse(screen,(32,70,80),(cx+dx-56,cy+dy-18,112,36),1)
                pygame.draw.circle(screen,INK,(cx+dx,cy+dy),7)
            pygame.draw.polygon(screen,(40,66,84),[(cx,cy-52),(cx+52,cy),(cx,cy+52),(cx-52,cy)])
            pygame.draw.polygon(screen,TEAL,[(cx,cy-28),(cx+15,cy+9),(cx-15,cy+9)],2)
            text("01 / ACRO TRAINER",784,498,22,TEAL)
            text("PHYSIQUE 480 Hz     •     VUE FPV",746,534,15,MUTED)
            text("Simulation locale / Windows · macOS · Linux",68,638,15,MUTED)
        elif page=="radio":
            text("VOTRE RADIO. VOS RÉGLAGES.",60,120,42)
            text("Pocket : port USB de données → USB Joystick (HID).",60,180,18,MUTED)
            text(radio.device.get_name()[:75] if radio.device else "Aucune radio détectée. Branchez un câble USB de données.",60,216,22,TEAL)
            raw=radio.raw()
            if calibration is not None and len(raw)!=len(calibration["low"]):
                calibration=None
                notice="Connexion modifiée : recommencez la calibration."
            if calibration is not None:
                for i,v in enumerate(raw):
                    calibration["low"][i]=min(calibration["low"][i],v)
                    calibration["high"][i]=max(calibration["high"][i],v)
            for i,v in enumerate(raw[:8]):
                y=280+i*28
                text(f"AXE {i+1:02}   {v:+.2f}",70,y,15,MUTED)
                pygame.draw.rect(screen,(28,44,59),(230,y+4,280,10),border_radius=5)
                pygame.draw.rect(screen,TEAL,(230,y+4,max(1,int((v+1)*140)),10),border_radius=5)
            for j,(n,a) in enumerate(radio.axes.items()):
                y=280+j*62
                button((580,y,290,48),f"{n.upper()}  /  Axe {a.index+1}",("axis",n))
                button((890,y,200,48),"Inversé" if a.inverted else "Sens normal",("invert",n))
            text("1. Centrez les sticks (gaz au milieu), puis démarrez.",60,548,18,MUTED)
            text("2. Bougez les quatre axes à fond dans les deux sens, puis sauvegardez.",60,576,18,MUTED)
            button((60,620,180,52),"Retour","hangar")
            button((260,620,250,52),"Démarrer calibration","calibrate")
            button((530,620,210,52),"Sauvegarder","save")
            button((760,620,330,52),"Utiliser : "+menu.settings.input_mode,"input")
        else:
            title,widgets=legacy.PAGES[page](menu)
            text(title,60,108,28,TEAL)
            # Legacy settings pages use their own fixed coordinates, placed in a scroll-free content area.
            for w in widgets:
                if isinstance(w,legacy.Field):
                    w.y=190+(w.y-min_y)*.64
                elif isinstance(w,legacy.Button):
                    w.rect.y=640
                w.draw(screen,fonts[15],fonts[22])
            if page=="manual_setup":
                button((980,190,250,50),menu.settings.input_mode,"input")
                button((980,254,250,50),"Vue : "+("FPV" if menu.settings.fpv_fullscreen else "Extérieure"),"view")
        if notice:
            text(notice[:110],60,690,15,TEAL)
        pygame.display.flip()
        for event in pygame.event.get():
            radio.event(event)
            if event.type==pygame.QUIT:
                pygame.quit(); return None,menu.settings
            if event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE:
                if page=="hangar":
                    pygame.quit(); return None,menu.settings
                page="hangar"
            if page not in ("hangar","radio"):
                for w in widgets:
                    w.handle(event)
                if menu._done:
                    if menu.result in ("play","train") and importlib.util.find_spec("stable_baselines3") is None:
                        notice="Module IA absent : lancez python bootstrap.py --ai --install-only."
                        menu._done=False
                    else:
                        pygame.quit(); return menu.result,menu.settings
                if menu.page!=page:
                    page="hangar" if menu.page=="main" else menu.page
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                for rect,action in buttons:
                    if not rect.collidepoint(event.pos): continue
                    if isinstance(action,tuple):
                        a=radio.axes[action[1]]
                        if action[0]=="axis": a.index=(a.index+1)%max(1,len(raw))
                        else: a.inverted=not a.inverted
                        radio.calibrated=False
                        calibration=None
                        notice="Axes modifiés : refaites la calibration."
                    elif action=="calibrate" and raw:
                        calibration=dict(low=raw.copy(),high=raw.copy(),center=raw.copy())
                        notice="Calibration en cours : déplacez les sticks aux extrémités."
                    elif action=="save":
                        if calibration is None:
                            notice="Commencez une calibration avec la radio connectée."
                        elif any(a.index>=len(raw) or calibration["high"][a.index]-calibration["low"][a.index]<.5 or not calibration["low"][a.index]<calibration["center"][a.index]<calibration["high"][a.index] for a in radio.axes.values()) or len({a.index for a in radio.axes.values()})!=4:
                            notice="Vérifiez les 4 axes distincts, les centres et les courses complètes."
                        else:
                            for a in radio.axes.values():
                                a.low=calibration["low"][a.index];a.high=calibration["high"][a.index];a.center=calibration["center"][a.index]
                            try:
                                radio.save();menu.settings.input_mode="Radio USB"
                                notice="Calibration sauvegardée. Baissez les gaz avant le vol."
                                calibration=None
                            except OSError as exc:
                                notice=f"Sauvegarde impossible : {exc}"
                    elif action=="input":
                        menu.settings.input_mode="Radio USB" if menu.settings.input_mode=="Clavier" else "Clavier"
                    elif action=="view": menu.settings.fpv_fullscreen=not menu.settings.fpv_fullscreen
                    elif action in ("manual_setup","play_setup","train_setup"):
                        menu.goto(action);page=action
                    elif action in ("hangar","radio"): page=action
                    break
        if page not in ("hangar","radio"):
            _,probe=legacy.PAGES[page](menu)
            min_y=min((w.y for w in probe if isinstance(w,legacy.Field)),default=0)
        clock.tick(60)
