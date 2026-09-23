# -*- coding: utf-8 -*-
"""
Created on Wed Oct  6 18:26:08 2021

@author: szoke
"""

class SCoPE_GUI:
    def __init__(self, gimbal_size=500, stick_zone=200, stick_max=1000, fullscreen=True, topmost=True):
        self.gimbal_size = gimbal_size
        self.stick_zone = [stick_zone,stick_zone,stick_zone,stick_zone]
        self.stick_max = stick_max
        self.gimbal_scaler = gimbal_size/(2*stick_max)
        self.gimbal_center = gimbal_size/2
        self.fullscreen = fullscreen
        self.topmost = topmost
        self.createGUI()
        
    def createGUI(self):
        import tkinter
        self.SCoPE_mainwindow = tkinter.Tk()
        self.SCoPE_mainwindow.attributes("-fullscreen",self.fullscreen)
        self.SCoPE_mainwindow.attributes("-topmost",self.topmost)
        self.SCoPE_mainwindow.configure(background="black")
        
        self.prompt_text = tkinter.StringVar()
        self.prompt_text.set("Press button on RC")
        self.buttonprompt = tkinter.Label(self.SCoPE_mainwindow, textvariable=self.prompt_text, font=("Arial", 72), fg="red", bg="black")
        self.buttonprompt.place(relx=0.5, rely=0.5, anchor="center")
        
        self.SCoPE_mainwindow.update_idletasks()
        self.SCoPE_mainwindow.update()
        
        self.counter_text = tkinter.StringVar()
        self.counter_text.set("Completed: 0\tMistakes: 0")   
        self.action_text = tkinter.StringVar()
        self.action_text.set("")
        
        self.window_width = self.SCoPE_mainwindow.winfo_width()
        self.window_height = self.SCoPE_mainwindow.winfo_height()
        
        self.action_label = tkinter.Label(self.SCoPE_mainwindow, textvariable=self.action_text, font=("Arial", 24), fg="white", bg="black")
        self.action_label.place(relx=0.5, rely=0.1, anchor="center")
        
        
        self.left_gimbal = tkinter.Canvas(self.SCoPE_mainwindow, height=self.gimbal_size, width=self.gimbal_size, bg="#333333", relief="flat", highlightthickness=0)
        self.left_gimbal.place(relx=0.3, rely=0.5, anchor="center")
        
        self.left_gimbal.create_line((self.gimbal_size/5),0,0,0,0,(self.gimbal_size/5), fill="white", width=20)
        self.left_gimbal.create_line((self.gimbal_size-(self.gimbal_size/5)),0,self.gimbal_size,0,self.gimbal_size,(self.gimbal_size/5), fill="white", width=20)
        self.left_gimbal.create_line((self.gimbal_size/5),self.gimbal_size,0,self.gimbal_size,0,(self.gimbal_size-(self.gimbal_size/5)), fill="white", width=20)
        self.left_gimbal.create_line((self.gimbal_size-(self.gimbal_size/5)),self.gimbal_size,self.gimbal_size,self.gimbal_size,self.gimbal_size,(self.gimbal_size-(self.gimbal_size/5)), fill="white", width=20)
        self.left_gimbal.create_line((self.gimbal_size/2),0,(self.gimbal_size/2),(self.gimbal_size/10), fill="white", width=10)
        self.left_gimbal.create_line(0,(self.gimbal_size/2),(self.gimbal_size/10),(self.gimbal_size/2), fill="white", width=10)
        self.left_gimbal.create_line((self.gimbal_size/2),self.gimbal_size,(self.gimbal_size/2),(self.gimbal_size-(self.gimbal_size/10)), fill="white", width=10)
        self.left_gimbal.create_line(self.gimbal_size,(self.gimbal_size/2),(self.gimbal_size-(self.gimbal_size/10)),(self.gimbal_size/2), fill="white", width=10)
        
        self.left_stick_zone = self.left_gimbal.create_oval(self.gimbal_center-int(self.stick_zone[0]*self.gimbal_scaler),self.gimbal_center-int(self.stick_zone[1]*self.gimbal_scaler),
                                                  self.gimbal_center+int(self.stick_zone[0]*self.gimbal_scaler),self.gimbal_center+int(self.stick_zone[1]*self.gimbal_scaler),outline="red",width=10, fill="red")
        self.left_stick = self.left_gimbal.create_oval(250-20, 250-20, 250+20, 250+20, outline="blue", fill="white", width=10)
        
        self.right_gimbal = tkinter.Canvas(self.SCoPE_mainwindow, height=self.gimbal_size, width=self.gimbal_size, bg="#333333", highlightthickness=0, relief="flat")
        self.right_gimbal.place(relx=0.7, rely=0.5, anchor="center")
        
        self.right_gimbal.create_line((self.gimbal_size/5),0,0,0,0,(self.gimbal_size/5), fill="white", width=20)
        self.right_gimbal.create_line((self.gimbal_size-(self.gimbal_size/5)),0,self.gimbal_size,0,self.gimbal_size,(self.gimbal_size/5), fill="white", width=20)
        self.right_gimbal.create_line((self.gimbal_size/5),self.gimbal_size,0,self.gimbal_size,0,(self.gimbal_size-(self.gimbal_size/5)), fill="white", width=20)
        self.right_gimbal.create_line((self.gimbal_size-(self.gimbal_size/5)),self.gimbal_size,self.gimbal_size,self.gimbal_size,self.gimbal_size,(self.gimbal_size-(self.gimbal_size/5)), fill="white", width=20)
        self.right_gimbal.create_line((self.gimbal_size/2),0,(self.gimbal_size/2),(self.gimbal_size/10), fill="white", width=10)
        self.right_gimbal.create_line(0,(self.gimbal_size/2),(self.gimbal_size/10),(self.gimbal_size/2), fill="white", width=10)
        self.right_gimbal.create_line((self.gimbal_size/2),self.gimbal_size,(self.gimbal_size/2),(self.gimbal_size-(self.gimbal_size/10)), fill="white", width=10)
        self.right_gimbal.create_line(self.gimbal_size,(self.gimbal_size/2),(self.gimbal_size-(self.gimbal_size/10)),(self.gimbal_size/2), fill="white", width=10)
        
        self.right_stick_zone = self.right_gimbal.create_oval(self.gimbal_center-int(self.stick_zone[3]*self.gimbal_scaler),self.gimbal_center-int(self.stick_zone[2]*self.gimbal_scaler),
                                                  self.gimbal_center+int(self.stick_zone[3]*self.gimbal_scaler),self.gimbal_center+int(self.stick_zone[2]*self.gimbal_scaler),outline="red",width=10, fill="red")
        self.right_stick = self.right_gimbal.create_oval(250-20, 250-20, 250+20, 250+20, outline="blue", fill="white", width=10)
        
        self.counter_label = tkinter.Label(self.SCoPE_mainwindow, textvariable=self.counter_text, font=("Arial", 24), fg="white", bg="black")
        self.counter_label.place(relx=0.5, rely=0.9, anchor="center")
        
    def updateStickZones(self,zone_posxy):
        self.left_gimbal.coords(self.left_stick_zone,int(((zone_posxy[0]+self.stick_max)-self.stick_zone[0])*self.gimbal_scaler),500-int(((zone_posxy[1]+self.stick_max)-self.stick_zone[1])*self.gimbal_scaler),
                                          int(((zone_posxy[0]+self.stick_max)+self.stick_zone[0])*self.gimbal_scaler),500-int(((zone_posxy[1]+self.stick_max)+self.stick_zone[1])*self.gimbal_scaler))
        self.right_gimbal.coords(self.right_stick_zone,int(((zone_posxy[3]+self.stick_max)-self.stick_zone[3])*self.gimbal_scaler),500-int(((zone_posxy[2]+self.stick_max)-self.stick_zone[2])*self.gimbal_scaler),
                                          int(((zone_posxy[3]+self.stick_max)+self.stick_zone[3])*self.gimbal_scaler),500-int(((zone_posxy[2]+self.stick_max)+self.stick_zone[2])*self.gimbal_scaler)) 
    
    def calculateStickPosition(self,stick_axes):
        sticks_posxy = [0,0,0,0]
        sticks_posxy[0] = int((stick_axes[0]+self.stick_max)*self.gimbal_scaler)
        sticks_posxy[1] = (self.gimbal_size-int((stick_axes[1]+self.stick_max)*self.gimbal_scaler))   
        sticks_posxy[2] = int((stick_axes[3]+self.stick_max)*self.gimbal_scaler)
        sticks_posxy[3] = (self.gimbal_size-int((stick_axes[2]+self.stick_max)*self.gimbal_scaler)) 
        return sticks_posxy  
    
    def updateStickPosition(self,stick_posxy):
        self.left_gimbal.coords(self.left_stick,(stick_posxy[0]-20),(stick_posxy[1]-20),(stick_posxy[0]+20),(stick_posxy[1]+20))
        self.right_gimbal.coords(self.right_stick,(stick_posxy[2]-20),(stick_posxy[3]-20),(stick_posxy[2]+20),(stick_posxy[3]+20))
    
    def updateZoneColor(self,zone_color):
        self.left_gimbal.itemconfig(self.left_stick_zone, outline=zone_color, fill=zone_color)
        self.right_gimbal.itemconfig(self.right_stick_zone, outline=zone_color, fill=zone_color)
        
    