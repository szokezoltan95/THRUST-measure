# -*- coding: utf-8 -*-
"""
Created on Fri Sep 24 09:10:34 2021

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
from SCoPE_GUI import SCoPE_GUI  


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
    
def requestNewAction(difficulty,shuffle_sequence,action_shuffle):
    if difficulty == "EASY":
        if shuffle_sequence < 15:
            shuffle_sequence +=1
        else:
            shuffle_sequence = 0
            random.shuffle(action_shuffle)
        action_request = actions[action_shuffle[shuffle_sequence]]
        
    elif difficulty == "MEDIUM":
        stick_choice = random.choice([0,1])
        deflx_choice = random.choice([-stick_max,(-stick_max/2),0,(stick_max/2),stick_max])
        defly_choice = random.choice([-stick_max,(-stick_max/2),0,(stick_max/2),stick_max])
        if stick_choice == 0:
            action_request = [deflx_choice,defly_choice,0,0]
        elif stick_choice == 1:
            action_request = [0,0,deflx_choice,defly_choice]
    
    elif difficulty == "HARD":
        aile_choice = random.choice([-stick_max,(-stick_max/2),0,(stick_max/2),stick_max])
        elev_choice = random.choice([-stick_max,(-stick_max/2),0,(stick_max/2),stick_max])
        thro_choice = random.choice([-stick_max,(-stick_max/2),0,(stick_max/2),stick_max])
        rudd_choice = random.choice([-stick_max,(-stick_max/2),0,(stick_max/2),stick_max])
        action_request = [aile_choice,elev_choice,thro_choice,rudd_choice]
    
    elif difficulty == "ULTRA":
        action_request = [random.randint(-1000,1000),random.randint(-1000,1000),random.randint(-1000,1000),random.randint(-1000,1000)]
    
    else:
        print("Difficulty selection error. Exiting...")
        sys.exit()
    
    print("Action:",action_request, end="")
    return action_request, shuffle_sequence

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
    
    global actions
    global stick_max
    chmap = ("AILE","ELEV","THRO","RUDD","LEVR","BUTT","SIDL","SIDR")
    acmap = ("AREQ","EREQ","TREQ","RREQ","IRRS")
    evmap = ("Time[s]","Action","Completed?","Total mistakes")
    stmap = ("Time[s]","AMEA","AMED","ASTD","EMEA","EMED","ESTD","TMEA","TMED","TSTD","RMEA","RMED","RSTD")
    action_shuffle = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] #action permutator
    deadzone = [100,100,100,100] #action complete deadzone
    deadzone_np = np.array(deadzone)
    fps = 100 #pygame clock fps
    hold_time = 0.5*fps #in seconds   
    action_timeout = 3000000000  #in nanoseconds
    stick_max = 1000 #stick resolution scaler
    tx_cal_a = [0,0,0,0,0]
    tx_cal_m = [1818,-1923,1666,-1250,2083]
    actions = ([-stick_max,0,0,0],[stick_max,0,0,0],
                    [0,-stick_max,0,0],[0,stick_max,0,0],
                    [0,0,-stick_max,0],[0,0,stick_max,0],
                    [0,0,0,-stick_max],[0,0,0,stick_max],
                    [-stick_max,-stick_max,0,0],[stick_max,stick_max,0,0],
                    [stick_max,-stick_max,0,0],[-stick_max,stick_max,0,0],
                    [0,0,-stick_max,-stick_max],[0,0,stick_max,stick_max],
                    [0,0,stick_max,-stick_max],[0,0,-stick_max,stick_max])   
      
    home = str(Path.home())
    Path(home+"\\Documents\\SCoPE\\actions\\").mkdir(parents=True, exist_ok=True)
    Path(home+"\\Documents\\SCoPE\\graphs\\").mkdir(parents=True, exist_ok=True)
    Path(home+"\\Documents\\SCoPE\\logs\\").mkdir(parents=True, exist_ok=True)
    Path(home+"\\Documents\\SCoPE\\steps\\").mkdir(parents=True, exist_ok=True)
    
    
    """
    User settings:
    """    
    user = str(input("Enter your name: "))    
    difficulty = str(input("Select difficulty: \nEASY \t- Only full deflections, one stick at a time\nMEDIUM \t- Mid and full deflections, one stick at a time\nHARD \t- Mid and full deflections, two sticks together\nULTRA \t- Random deflections on all sticks\n\n")).upper()    
    while difficulty != "EASY" and difficulty != "MEDIUM" and difficulty != "HARD" and difficulty != "ULTRA":
        difficulty = str(input("Please type EASY, MEDIUM, HARD or ULTRA: ")).upper()        
    try:
        action_timeout_input = int(input("Enter action timeout in seconds (1-10, default 3): "))
        while action_timeout_input <1 or action_timeout_input >10:
            action_timeout_input = int(input("Please nter a number between 1 and 10: "))
    except:    
        print(f"{bcolors.FAIL}Incorrect or no entry, using default.{bcolors.ENDC}")
        input("Press Enter to continue")
        action_timeout_input = 3    
    action_timeout = action_timeout_input*1000000000 
    
    """
    Loading GUI
    """    
    GUI = SCoPE_GUI()
    
    """
    Joystick configuration
    """ 
    pygame.display.init()
    pygame.joystick.init()
    try:
        controller = pygame.joystick.Joystick(0)
        controller.init()
    except:
        GUI.SCoPE_mainwindow.destroy()
        print(f"{bcolors.FAIL}Joystick not found. Exiting...{bcolors.ENDC}")
        sys.exit()
    axes = controller.get_numaxes()
    axvalues = []
    for i in range(axes):
        axvalues.append(0)
    
    """
    Resetting Break axis
    """
    if controller.get_axis(5) > 0:
        print("Press button on RC")
    while controller.get_axis(5) > 0:
        pygame.event.pump()    
    """
    Countdown
    """
    for i in range(3,0,-1):
        GUI.prompt_text.set(str(i))
        GUI.SCoPE_mainwindow.update_idletasks()
        GUI.SCoPE_mainwindow.update()
        time.sleep(1)
    GUI.buttonprompt.destroy()
    
    """
    Setting up start parameters
    """
    now = datetime.now()
    file_datetime = now.strftime("%Y%m%d_%H%M%S")
    logfile_path = home+"\\Documents\\SCoPE\\logs\\SCoPE_log_"+user+"_"+difficulty+"_"+file_datetime+".txt"
    evlfile_path = home+"\\Documents\\SCoPE\\actions\\SCoPE_actions_"+user+"_"+difficulty+"_"+file_datetime+".txt"    
    
    logfile = open(logfile_path,"w")
    evlfile = open(evlfile_path,"w")
    
    print("Saving log to: "+logfile_path)
    print("Saving evaluation data to: "+evlfile_path)
    print(f"{bcolors.OKGREEN}LINK ACTIVE{bcolors.ENDC}")
    total_mistakes = 0
    total_completed = 0
    action_completed = False
    in_range = 0
    inzone_timer = 0
    shuffle_sequence = 0
    random.seed(time.time_ns())
    random.shuffle(action_shuffle)
    action_request, shuffle_sequence = requestNewAction(difficulty, shuffle_sequence, action_shuffle)
    action_request_np = np.array(action_request)
    GUI.updateStickZones(action_request)
    GUI.action_text.set("Action: "+str(action_request))  
    
    """
    Writing file header
    """
    logfile.write("TIME")
    for i in chmap:
        logfile.write("\t")
        logfile.write(i)
    for i in acmap:
        logfile.write("\t")
        logfile.write(i)
    logfile.write("\n")
    for i in chmap:
        logfile.write("0 \t")
    for i in acmap:
        logfile.write("0 \t")
    logfile.write("\n")    
    for i in evmap:
        if i == "Action":
            if difficulty == "EASY":
                evlfile.write(i)
            else:
                evlfile.write("AREQ\tEREQ\tTREQ\tRREQ")
        else:
            evlfile.write(i)
        evlfile.write("\t")
    evlfile.write("\n")
    
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
        GUI.SCoPE_mainwindow.update_idletasks()
        GUI.SCoPE_mainwindow.update()
        
        clk.tick(fps)
        sample_time = time.time_ns()
        # Get next pygame event
        pygame.event.pump()
        
        logfile.write(str((sample_time-start_time)/1000000000))
        
        axvalues[3] = int(controller.get_axis(0)*tx_cal_m[0])+tx_cal_a[0]
        axvalues[1] = int(controller.get_axis(1)*tx_cal_m[1])+tx_cal_a[1]
        axvalues[2] = int(controller.get_axis(2)*tx_cal_m[2])+tx_cal_a[2]
        axvalues[4] = int(controller.get_axis(3)*tx_cal_m[3])+tx_cal_a[3]
        axvalues[0] = int(controller.get_axis(4)*tx_cal_m[4])+tx_cal_a[4]
        
        
        for k in range(len(axvalues)):
            logfile.write('\t%+2.2f' % (axvalues[k]))
        for k in action_request:
            logfile.write('\t%+2.2f' % (k))
        logfile.write('\t')
        logfile.write(str(in_range))
        logfile.write("\n")
        axvalues_np = np.array(axvalues)
        
        if action_completed == True:
            action_request, shuffle_sequence = requestNewAction(difficulty,shuffle_sequence,action_shuffle)
            action_completed = False
            inzone_timer = 0
            GUI.updateZoneColor("red")
            GUI.updateStickZones(action_request)
            GUI.action_text.set("Action: "+str(action_request))
            action_request_np = np.array(action_request)
            action_start = sample_time   
                
        if action_completed == False:
            if all(axvalues_np[0:4] < (action_request_np[0:4]+deadzone_np[0:4])) and all(axvalues_np[0:4] > (action_request_np[0:4]-deadzone_np[0:4])):
                inzone_timer +=1
                in_range = 1
                GUI.updateZoneColor("green")
            else:
                inzone_timer = 0
                in_range = 0
                GUI.updateZoneColor("red")
                
            if inzone_timer >= hold_time:
                action_completed = True
                if difficulty == "EASY":
                    evlstring=str((sample_time-action_start)/1000000000)+"\t"+str(action_shuffle[shuffle_sequence])+"\t1\t"+str(total_mistakes)+"\n"
                else:
                    evlstring=str((sample_time-action_start)/1000000000)+"\t"+str(action_request[0])+"\t"+str(action_request[1])+"\t"+str(action_request[2])+"\t"+str(action_request[3])+"\t1\t"+str(total_mistakes)+"\n"
                evlfile.write(evlstring)
                total_completed+=1
                print(f" {bcolors.OKGREEN}OK{bcolors.ENDC}")
                GUI.counter_text.set("Completed: "+str(total_completed)+"\tMistakes: "+str(total_mistakes))
                #print("Total completed: ",total_completed,"\tMistakes: ",total_mistakes)
            elif sample_time-action_start >= action_timeout:
                action_completed = True
                total_mistakes+=1
                if difficulty == "EASY":    
                    evlstring=str((sample_time-action_start)/1000000000)+"\t"+str(action_shuffle[shuffle_sequence])+"\t0\t"+str(total_mistakes)+"\n"
                else:
                    evlstring=str((sample_time-action_start)/1000000000)+"\t"+str(action_request[0])+"\t"+str(action_request[1])+"\t"+str(action_request[2])+"\t"+str(action_request[3])+"\t1\t"+str(total_mistakes)+"\n"
                evlfile.write(evlstring)
                print(f" {bcolors.FAIL}FAIL{bcolors.ENDC}")
                GUI.counter_text.set("Completed:"+str(total_completed)+"\tMistakes:"+str(total_mistakes))
                #print("Total completed: ",total_completed,"\tMistakes: ",total_mistakes)
        
        GUI.updateStickPosition(GUI.calculateStickPosition(axvalues))
    
    
        #if controller.get_axis(5) > 0:
            #break
    
    """
    Ending measurement loop
    """       
    print(f"\n{bcolors.OKBLUE}LINK CLOSED{bcolors.ENDC}")
    logfile.close()
    print("Log saved to: "+logfile_path)
    evlfile.close()
    print("Evaluation data saved to: "+evlfile_path)
    
    """
    Closing GUI
    """
    GUI.SCoPE_mainwindow.destroy()
    
    """
    Starting evaluation
    """
    print(f"Total actions completed: {bcolors.OKGREEN}",total_completed,bcolors.ENDC)
    print(f"Total mistakes: {bcolors.FAIL}",total_mistakes,bcolors.ENDC)
    print("Evaluating step response from data ",logfile_path)
    datafile = pd.read_csv(logfile_path,sep='\t')
    
    """
    Calculating step responses
    """
    print("Calculating channel ELEV ", end="")
    try:
        step_aile, step_aile_median, step_aile_mean, step_aile_std = evaluateStepResponse(datafile, "AILE", "AREQ")
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Calculating channel AILE ", end="")
    try:
        step_elev, step_elev_median, step_elev_mean, step_elev_std = evaluateStepResponse(datafile, "ELEV", "EREQ")
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Calculating channel THRO ", end="")
    try:
        step_thro, step_thro_median, step_thro_mean, step_thro_std = evaluateStepResponse(datafile, "THRO", "TREQ")
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Calculating channel RUDD ", end="")
    try:
        step_rudd, step_rudd_median, step_rudd_mean, step_rudd_std = evaluateStepResponse(datafile, "RUDD", "RREQ")
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    """
    Saving data to file
    """
    print("Saving step response data to file...", end="")
    try:    
        step_path = home+"\\Documents\\SCoPE\\steps\\"+user+"_"+file_datetime+".txt"
        stepfile = open(step_path, "w")
        csvdump = [[i/100 for i in range(200)],
                   step_aile_mean[:200], step_aile_median[:200], step_aile_std[:200],
                   step_elev_mean[:200], step_elev_median[:200], step_elev_std[:200],
                   step_thro_mean[:200], step_thro_median[:200], step_thro_std[:200],
                   step_rudd_mean[:200], step_rudd_median[:200], step_rudd_std[:200],]
            
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
        stepfile.close()
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    """
    Plotting graphs
    """
    print("Plotting step response graphs...", end="")
    fig = plt.figure(figsize = (15,10))
    ax1 = plt.subplot2grid((2,2),(0,0))
    ax2 = plt.subplot2grid((2,2),(0,1))
    ax4 = plt.subplot2grid((2,2),(1,0))
    ax3 = plt.subplot2grid((2,2),(1,1))
    graph_title = user+"_"+difficulty
    fig.suptitle(graph_title)
    
    try:    
        x1 = [i/100 for i in range(0,len(step_aile_mean))]
        ax1.plot(x1, step_aile_median, color="blue", label="Median")
        ax1.plot(x1, step_aile_mean, color="red", label="Mean")
        ax1.fill_between(x1, step_aile_mean-step_aile_std, step_aile_mean+step_aile_std,
                         color="red", label="Stdev", alpha=0.3)
        ax1.set_xlim(0,2)
        ax1.set_ylim(-0.2, 1.3)
        ax1.legend(loc="lower right")
        ax1.grid()
        ax1.set_ylabel("Step response")
        ax1.set_xlabel("Time [s]")
        ax1.set_title("AILE")
        
        x2 = [i/100 for i in range(0,len(step_elev_mean))]
        ax2.plot(x2, step_elev_median, color="blue", label="Median")
        ax2.plot(x2, step_elev_mean, color="red", label="Mean")
        ax2.fill_between(x2, step_elev_mean-step_elev_std, step_elev_mean+step_elev_std,
                         color="red", label="Stdev", alpha=0.3)
        ax2.set_xlim(0,2)
        ax2.set_ylim(-0.2, 1.3)
        ax2.legend(loc="lower right")
        ax2.grid()
        ax2.set_ylabel("Step response")
        ax2.set_xlabel("Time [s]")
        ax2.set_title("ELEV")
        
        x3 = [i/100 for i in range(0,len(step_thro_mean))]
        ax3.plot(x3, step_thro_median, color="blue", label="Median")
        ax3.plot(x3, step_thro_mean, color="red", label="Mean")
        ax3.fill_between(x3, step_thro_mean-step_thro_std, step_thro_mean+step_thro_std,
                         color="red", label="Stdev", alpha=0.3)
        ax3.set_xlim(0,2)
        ax3.set_ylim(-0.2, 1.3)
        ax3.legend(loc="lower right")
        ax3.grid()
        ax3.set_ylabel("Step response")
        ax3.set_xlabel("Time [s]")
        ax3.set_title("THRO")
        
        x4 = [i/100 for i in range(0,len(step_rudd_mean))]
        ax4.plot(x4, step_rudd_median, color="blue", label="Median")
        ax4.plot(x4, step_rudd_mean, color="red", label="Mean")
        ax4.fill_between(x4, step_rudd_mean-step_rudd_std, step_rudd_mean+step_rudd_std,
                         color="red", label="Stdev", alpha=0.3)
        ax4.set_xlim(0,2)
        ax4.set_ylim(-0.2, 1.3)
        ax4.legend(loc="lower right")
        ax4.grid()
        ax4.set_ylabel("Step response")
        ax4.set_xlabel("Time [s]")
        ax4.set_title("RUDD")
        
        plt.tight_layout()
        
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
    
    print("Saving graph...", end="")
    try:
        savepath = home+"\\Documents\\SCoPE\\graphs\\"+graph_title+"_"+file_datetime+".pdf"
        plt.savefig(savepath)
        print(f"{bcolors.OKGREEN}COMPLETE{bcolors.ENDC}")
        print("Graph saved to",savepath)
        os.startfile(savepath)
    except:
        print(f"{bcolors.FAIL}FAILED{bcolors.ENDC}")
        
    print("Step response evaluation finished.")

if __name__ == "__main__":
    main()
    sys.exit()


