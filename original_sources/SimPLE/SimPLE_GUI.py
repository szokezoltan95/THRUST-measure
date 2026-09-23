# -*- coding: utf-8 -*-
"""
Created on Tue Jul  5 17:38:08 2022

@author: szoke
"""

class SimPLE_GUI:
    def __init__(self, zoom=500, stick_zone=(100,100), field_offset=(750,1000), fullscreen=True, topmost=True):
        self.fullscreen = fullscreen
        self.topmost = topmost
        self.zoom = zoom
        self.stick_zone = stick_zone
        self.field_offset = field_offset
        self.createGUI()
        
        
        
    def createGUI(self):
        import tkinter
        self.SimPLE_mainwindow = tkinter.Tk()
        self.SimPLE_mainwindow.attributes("-fullscreen",self.fullscreen)
        self.SimPLE_mainwindow.attributes("-topmost",self.topmost)
        self.SimPLE_mainwindow.configure(background="black")

        self.buttonprompt = tkinter.Label(self.SimPLE_mainwindow, text = "Press button on RC", font=("Arial", 72), fg="red", bg="black")
        self.buttonprompt.place(relx=0.5, rely=0.9, anchor="center")

        self.SimPLE_mainwindow.update_idletasks()
        self.SimPLE_mainwindow.update()

        self.window_width = self.SimPLE_mainwindow.winfo_width()
        self.window_height = self.SimPLE_mainwindow.winfo_height()

        self.action_text = tkinter.StringVar()
        self.action_text.set("")

        self.field = tkinter.Canvas(self.SimPLE_mainwindow, height=1000, width=1500, bg="#333333", relief="flat", highlightthickness=0)
        self.field.place(relx=0.5, rely=0, anchor="n")
        self.field_bg = self.field.create_image(0, 0, anchor="nw", image=tkinter.PhotoImage(file='background.png'))

        self.copter_zone = self.field.create_oval(self.field_offset[0]-50, self.field_offset[1]-50, self.field_offset[0]+50, self.field_offset[1]+50, outline="red" ,width=10, fill="red")
        self.copter_masspoint = self.field.create_oval(750-25, 500-25, 750+25, 1000+25, fill="blue")
        self.copter_line = self.field.create_line(750, 500, 750-50, 500, fill="white", width=10)

        self.action_label = tkinter.Label(self.SimPLE_mainwindow, textvariable=self.action_text, font=("Arial", 24), fg="white", bg="black")
        self.action_label.place(relx=0.5, rely=1, anchor="s")

    def updateCopterPosition(self,copter_posxy,angle_sincos):
        self.field.coords(self.copter_masspoint,copter_posxy[0]*self.zoom+self.field_offset[0]-25,-copter_posxy[1]*self.zoom+self.field_offset[1]-25,copter_posxy[0]*self.zoom+self.field_offset[0]+25,-copter_posxy[1]*self.zoom+self.field_offset[1]+25)
        self.field.coords(self.copter_line,copter_posxy[0]*self.zoom+self.field_offset[0], -copter_posxy[1]*self.zoom+self.field_offset[1], copter_posxy[0]*self.zoom+50*angle_sincos[0]+self.field_offset[0], -(copter_posxy[1]*self.zoom+50*angle_sincos[1])+self.field_offset[1])
 
    def updateActionZone(self,zone_posxy):
        self.field.coords(self.copter_zone,int((zone_posxy[0]*self.zoom+self.field_offset[0])-self.stick_zone[0]),self.field_offset[1]-int(zone_posxy[1]*self.zoom)-self.stick_zone[1],
                                              int((zone_posxy[0]*self.zoom+self.field_offset[0])+self.stick_zone[0]),self.field_offset[1]-int(zone_posxy[1]*self.zoom)+self.stick_zone[1])

    def updateZoneColor(self,zone_color):
        self.field.itemconfig(self.copter_zone, outline=zone_color, fill=zone_color)  