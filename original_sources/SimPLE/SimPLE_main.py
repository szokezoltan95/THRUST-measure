# -*- coding: utf-8 -*-
"""
Created on Mon Oct  4 09:28:34 2021

@author: szoke
"""

import time
import sys, os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import random
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from itertools import zip_longest
from datetime import datetime
import math
from SimPLE_GUI import *

class Copter:
    """accxy - m*s**-2, velxy - m*s**-1, posxy - m, angle - rad, mass - kg, maxtrust - N""" 
    def __init__(self,accxy=[0,0],velxy=[0,0],posxy=[0,0],angle=0,mass=0.8,maxthrust=16,drag=0.3):
        self.accxy = accxy
        self.velxy = velxy
        self.posxy = posxy
        self.angle = angle
        self.mass = mass
        self.maxthrust = maxthrust
        self.drag = drag
        
    def updateState(self,dt,thrust_set):
        new_accxy=[0,0]
        new_velxy=[0,0]
        new_posxy=[0,0]
        
        if self.posxy[1] < 0:
            new_posxy[1] = 0
            new_posxy[0] = self.posxy[0]
            new_velxy[0] = self.velxy[0]/2
            new_velxy[1] = -self.velxy[1]/2
            
        else:
            for i in range(2):
                
                if i == 0:
                    self.accxy[i] = math.sin(self.angle)*thrust_set*self.maxthrust/self.mass - self.drag*(self.velxy[i]*abs(self.velxy[i]))
                    
                elif i == 1:
                    self.accxy[i] = math.cos(self.angle)*thrust_set*self.maxthrust/self.mass - (9.81 + self.drag*(self.velxy[i]*abs(self.velxy[i])))
    
                new_velxy[i] = self.velxy[i] + self.accxy[i]*dt
                new_posxy[i] = self.posxy[i] + new_velxy[i]*dt + 0.5*new_accxy[i]*(dt**2)
            
        self.accxy = new_accxy
        self.velxy = new_velxy
        self.posxy = new_posxy
    
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[44m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[42m'
    WARNING = '\033[93m'
    FAIL = '\033[43m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'    


def requestNewAction(zoomlevel):
    acreq = [int(random.randint(-750,750))/zoomlevel,int(random.randint(0,1000))/zoomlevel]
    return acreq

def evaluateStepResponse(data_in, channel, creq):
    data_out = [[]]
    j=0
    k=0
    n_gain = 1
    n_offset = 0
    while data_in[creq][k]==0:
        k+=1
    
    for i in range(k,len(data_in)):
        if data_in[creq][i-1] != data_in[creq][i]:
            norm = abs((data_in[creq][i]-data_in[creq][i-1]))
            n_gain = 1/norm
            if data_in[creq][i] < data_in[creq][i-1]:
                n_gain = -n_gain
            n_offset = data_in[creq][i-1]
            data_out.append([])
            j+=1
            print(".",end="")
        data_out[j].append(((data_in[channel][i])-n_offset)*n_gain)
    
    data_median = np.nanmedian(np.array(list(zip_longest(*data_out)),dtype=float),axis=1)
    data_mean = np.nanmean(np.array(list(zip_longest(*data_out)),dtype=float),axis=1)
    data_std = np.nanstd(np.array(list(zip_longest(*data_out)),dtype=float),axis=1)
    
    return data_out, data_median, data_mean, data_std



def main():
    lgmap = ("Time[s]","POSX","POSY","REQX","REQY")
    stmap = ("Time[s]","XMEA","XMED","XSTD","YMEA","YMED","YSTD")
    zoom = 500
    deadzone = (50/zoom,50/zoom) #action complete deadzone
    deadzone_np = np.array(deadzone)
    stick_max = 1000
    fps = 100 #pygame clock fps
    hold_time = 1*fps #in seconds   
    action_timeout = 5000000000  #in nanoseconds       
    resets = 0
    reset_switch = False
    
    home = str(Path.home())
    
    Path(home+"\\Documents\\SimPLE\\actions\\").mkdir(parents=True, exist_ok=True)
    Path(home+"\\Documents\\SimPLE\\graphs\\").mkdir(parents=True, exist_ok=True)
    Path(home+"\\Documents\\SimPLE\\logs\\").mkdir(parents=True, exist_ok=True)
    Path(home+"\\Documents\\SimPLE\\steps\\").mkdir(parents=True, exist_ok=True)
    
    user = str(input("Enter your name: "))

    """
    Loading GUI and Copter
    """    
    GUI = SimPLE_GUI()
    copter = Copter()    
    
    """
    Joystick configuration
    """
    pygame.display.init()
    pygame.joystick.init()
    try:
        controller = pygame.joystick.Joystick(0)
        controller.init()
    except:
        GUI.SimPLE_mainwindow.destroy()
        print(f"{bcolors.FAIL}Joystick not found. Exiting...{bcolors.ENDC}")
        sys.exit()
    
    """
    Setting up axes:
    """
    axes = controller.get_numaxes()
    axvalues =[]
    for i in range(axes):
        axvalues.append(0)
    
    """
    Resetting Break axis:
    """
    if controller.get_axis(5) > 0:
        print("Press button on RC")
    while controller.get_axis(5) > 0:
        pygame.event.pump()
    
    GUI.buttonprompt.destroy()
    
    """
    Setting up start parameters:
    """
    action_completed = False
    inzone_timer = 0
    random.seed(time.time_ns())
    action_request = requestNewAction(zoom)
    action_request_np = np.array(action_request)
    GUI.updateActionZone(action_request)
    actions_completed = 0
    now = datetime.now()
    file_datetime = now.strftime("%Y%m%d_%H%M%S")
    logfile_path = home+"\\Documents\\SimPLE\\logs\\SimPLE_log_"+user+"_"+file_datetime+".txt"
    
    """
    Writing file header
    """
    log = open(logfile_path, "w")
    for i in lgmap:
        log.write(str(i)+"\t")
    log.write("\n")
    for i in lgmap:
        log.write("0 \t")
    log.write("\n")
    
    """
    Starting timers
    """
    clk = pygame.time.Clock()
    start_time = time.time_ns()
    sample_time = start_time
    action_start = sample_time
    
    """
    Measurement loop:
    """
    while True:
        GUI.SimPLE_mainwindow.update_idletasks()
        GUI.SimPLE_mainwindow.update()
        
        system_dt = clk.tick(fps)/1000
        sample_time = time.time_ns()
        pygame.event.pump()
        
        log.write(str((sample_time-start_time)/1000000000))
        
        for k in range(axes):
            axvalues[k] = int(controller.get_axis(k)*stick_max)
        
        copter.angle=axvalues[0]*math.radians(90)/1000
        thrust=(axvalues[2]+stick_max)/(2*stick_max)
        
        copter.updateState(system_dt, thrust)
        copter_pos_np = np.array(copter.posxy)
        
        GUI.updateCopterPosition(copter.posxy,[math.sin(copter.angle),math.cos(copter.angle)])
   
        for i in range(2):
            log.write('\t%+2.2f' % (copter.posxy[i]))
        for i in range(2):
            log.write('\t%+2.2f' % (action_request[i]))
        log.write("\n")
       
        
        GUI.action_text.set("Actions completed: "+str(actions_completed)+"\t Resets: "+str(resets))
    
        if action_completed == True:
            action_completed = False
            actions_completed +=1
            inzone_timer = 0
            old_action = action_request
            while (old_action[0] < action_request[0]+0.5 and old_action[0] > action_request[0]-0.5) or (old_action[1] < action_request[1]+0.5 and old_action[1] > action_request[1]-0.5):  
                action_request=requestNewAction(zoom)
            GUI.updateZoneColor("red")
            GUI.updateActionZone(action_request)
            action_request_np = np.array(action_request)
            action_start = sample_time
            
                
        if action_completed == False:
            if all(copter_pos_np[0:2] < (action_request_np[0:2]+deadzone_np[0:2])) and all(copter_pos_np[0:2] > (action_request_np[0:2]-deadzone_np[0:2])):
                inzone_timer +=1
                GUI.updateZoneColor("green")
            else:
                inzone_timer = 0
                GUI.updateZoneColor("red")
                
            if inzone_timer >= hold_time:
                action_completed = True
            
            if sample_time-action_start >= action_timeout:
                action_completed = True

        if controller.get_axis(5) > 0:
            break
        if controller.get_axis(4) > 0:
            reset_switch = True
            copter.posxy = [0,0]
        if reset_switch == True:
            if controller.get_axis(4) < 0:
                resets += 1
                reset_switch = False

    """
    Ending measurement loop
    """       
    print(f"\n{bcolors.OKBLUE}LINK CLOSED{bcolors.ENDC}")
    log.close()
    print("Log saved to: "+logfile_path)

    """
    Closing GUI
    """
    GUI.SimPLE_mainwindow.destroy()
    
    """
    Starting evaluation
    """
    print("Evaluating step response from data ",logfile_path)
    datafile = pd.read_csv(logfile_path,sep='\t')

    print("Calculating x axis", end="")
    try:
        step_x, step_x_median, step_x_mean, step_x_std = evaluateStepResponse(datafile, "POSX", "REQX")
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Calculating y axis ", end="")
    try:
        step_y, step_y_median, step_y_mean, step_y_std = evaluateStepResponse(datafile, "POSY", "REQY")
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Saving step response data to file...", end="")
    try:    
        step_path = home+"\\Documents\\SimPLE\\steps\\"+user+"_"+file_datetime+".txt"
        stepfile = open(step_path, "w")
        csvdump = [[i/100 for i in range(200)],
                   step_x_mean[:1000], step_x_median[:1000], step_x_std[:1000],
                   step_y_mean[:1000], step_y_median[:1000], step_y_std[:1000]]     
        for i in stmap:
            stepfile.write(i)
            stepfile.write("\t")
        stepfile.write("\n")
        for i in range(200):
            for j in csvdump:
                stepfile.write(str(j[i]))
                stepfile.write("\t")
            stepfile.write("\n")
        stepfile.close()
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Plotting step response graphs...", end="")
    fig = plt.figure(figsize = (15,10))
    ax1 = plt.subplot2grid((2,1),(0,0))
    ax2 = plt.subplot2grid((2,1),(1,0))
    
    graph_title = user
    fig.suptitle(graph_title)
    
    try:    
        x1 = [i/100 for i in range(0,len(step_x_mean))]
        ax1.plot(x1, step_x_median, color="blue", label="Median")
        ax1.plot(x1, step_x_mean, color="red", label="Mean")
        ax1.fill_between(x1, step_x_mean-step_x_std, step_x_mean+step_x_std,
                         color="red", label="Stdev", alpha=0.3)
        ax1.set_xlim(0,5)
        ax1.set_ylim(-0.2, 1.3)
        ax1.legend(loc="lower right")
        ax1.grid()
        ax1.set_ylabel("Step response")
        ax1.set_xlabel("Time [s]")
        ax1.set_title("X axis")
        
        x2 = [i/100 for i in range(0,len(step_y_mean))]
        ax2.plot(x2, step_y_median, color="blue", label="Median")
        ax2.plot(x2, step_y_mean, color="red", label="Mean")
        ax2.fill_between(x2, step_y_mean-step_y_std, step_y_mean+step_y_std,
                         color="red", label="Stdev", alpha=0.3)
        ax2.set_xlim(0,5)
        ax2.set_ylim(-0.2, 1.3)
        ax2.legend(loc="lower right")
        ax2.grid()
        ax2.set_ylabel("Step response")
        ax2.set_xlabel("Time [s]")
        ax2.set_title("Y axis")
     
        plt.tight_layout()
        
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Saving graph...", end="")
    try:
        savepath = home+"\\Documents\\SimPLE\\graphs\\"+graph_title+"_"+file_datetime+".pdf"
        plt.savefig(savepath)
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
        print("Graph saved to",savepath)
        os.startfile(savepath)
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
        
    print("Step response evaluation finished.")
      
    sys.exit()

if __name__ == "__main__":
    main()
    sys.exit()
