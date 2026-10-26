"""Compact flight instruments; F1 exposes the detailed engineering overlay."""
import math
import numpy as np
import pygame
from .hud import HUDOverlay

class FlightHUD:
    def __init__(self,screen):
        self.screen=screen
        self.details=HUDOverlay(screen)
        self.expanded=False
        self.small=pygame.font.SysFont("Segoe UI",15)
        self.medium=pygame.font.SysFont("Segoe UI",22,bold=True)
        self.large=pygame.font.SysFont("Segoe UI",34,bold=True)

    def handle_event(self,event,controls):
        if event.type==pygame.KEYDOWN and event.key==pygame.K_F1:
            self.expanded=not self.expanded
            return True
        return self.details.handle_event(event,controls) if self.expanded else False

    def draw(self,sticks,state,target_pos,sim_time,fps=0.,fpv_surface=None,fpv_pitch=0.,controls=None,motors_disabled=False):
        if self.expanded:
            self.details.draw(sticks,state,target_pos,sim_time,fps=fps,fpv_surface=fpv_surface,fpv_pitch=fpv_pitch,controls=controls,motors_disabled=motors_disabled)
            return
        screen=self.screen
        w,h=screen.get_size()
        ink=(230,243,250);teal=(64,231,197);muted=(137,164,183)
        def text(value,x,y,font=None,color=ink):
            screen.blit((font or self.small).render(value,True,color),(x,y))
        def panel(rect):
            layer=pygame.Surface((rect[2],rect[3]),pygame.SRCALPHA)
            layer.fill((8,17,28,208))
            screen.blit(layer,rect[:2])
            pygame.draw.rect(screen,(38,65,82),rect,1,border_radius=6)
        panel((24,20,280,66))
        text("S K Y M I N D",40,29,self.medium)
        text("VOL LIBRE / ACRO",40,59,color=teal)
        panel((w-244,20,220,66))
        text(f"{int(sim_time)//60:02}:{int(sim_time)%60:02}  /  {fps:.0f} FPS",w-228,30,self.medium)
        text("USB RADIO" if controls and controls.radio else "CLAVIER",w-228,60,color=teal)
        # A restrained FPV reticle, with no fake attitude or telemetry.
        cx,cy=w//2,h//2
        for sign in (-1,1):
            pygame.draw.line(screen,teal,(cx+sign*12,cy),(cx+sign*28,cy),2)
        pygame.draw.circle(screen,ink,(cx,cy),2)
        panel((24,h-136,w-48,112))
        speed=float(np.linalg.norm(state["lin_vel"]))*3.6
        distance=float(np.linalg.norm(target_pos-state["pos"]))
        for x,label,value in ((44,"VITESSE",f"{speed:.1f} km/h"),(240,"ALTITUDE",f"{state['pos'][2]:.1f} m"),(436,"CIBLE",f"{distance:.1f} m"),(632,"GAZ",f"{sticks.throttle*100:.0f} %")):
            text(label,x,h-122,color=muted)
            text(value,x,h-101,self.large)
        text("R  Réinitialiser     V  Changer de vue     F1  Réglages avancés     ÉCHAP  Hangar",44,h-52,color=muted)
        for x,ax,ay in ((w-180,sticks.yaw,sticks.throttle*2-1),(w-85,sticks.roll,sticks.pitch)):
            y=h-88
            pygame.draw.circle(screen,(51,80,96),(x,y),31,1)
            pygame.draw.line(screen,(51,80,96),(x-31,y),(x+31,y))
            pygame.draw.line(screen,(51,80,96),(x,y-31),(x,y+31))
            pygame.draw.circle(screen,teal,(x+int(ax*26),y-int(ay*26)),5)
        if motors_disabled:
            panel((w//2-210,110,420,48))
            text("CRASH  /  R POUR REPARTIR",w//2-185,122,self.medium,(255,110,105))
