#!/usr/bin/env python

#Code compiled by Michael J. Mastalish, 6/30/21

import requests
import json
import sys

 
from BaseDriver import LabberDriver
import datetime


class Driver(LabberDriver):

    
    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""
        if quant.name == 'Get Temp':
            resp = requests.get('http://192.168.10.103:47101/v1/sampleChamber/temperatureControllers/user1/thermometer/properties/sample')
            #sample thermometer is controlled through user1
            sampleDict = json.loads(resp.content.decode('utf-8'))['sample']
            actualTemp = sampleDict['temperature']
            value = actualTemp
        return value 
    
    def performSetValue(self, quant, value, sweepRate=0.0, options={}):                         
        """Perform the Set Value instrument operation"""
        if quant.name == 'Set Temp':
            
            cutoff = 290.0 #Defines the cutoff temperature to control warmup and cooldown processes.

            resp   = requests.get('http://192.168.10.103:47101/v1/controller/properties/systemGoal')
            state = json.loads(resp.content.decode('utf-8'))['systemGoal'] #This gives the current state of the cryostat
            target = float(value) #This gives the target value that the user has provided through labber
            
            if state == 'Cooldown':
                if target > cutoff:
                    resp = requests.post('http://192.168.10.103:47101/v1/controller/methods/abortGoal()')
                    resp = requests.post('http://192.168.10.103:47101/v1/controller/methods/warmup()')
                    resp = requests.put("http://192.168.10.103:47101/v1/controller/properties/platformTargetTemperature", json={"platformTargetTemperature": target})
                else:
                    resp = requests.put("http://192.168.10.103:47101/v1/controller/properties/platformTargetTemperature", json={"platformTargetTemperature": target})
                    #resp   = requests.get('http://192.168.10.102:47101/v1/controller/properties/platformTargetTemperature')
                    #newSetpoint = json.loads(resp.content.decode('utf-8'))['platformTargetTemperature']
            else:
                if target < cutoff:
                    resp = requests.post('http://192.168.10.103:47101/v1/controller/methods/abortGoal()')
                    resp = requests.put("http://192.168.10.103:47101/v1/controller/properties/platformTargetTemperature", json={"platformTargetTemperature": target})
                    #resp   = requests.get('http://192.168.10.103:47101/v1/controller/properties/platformTargetTemperature')
                    #newSetpoint = json.loads(resp.content.decode('utf-8'))['platformTargetTemperature']
                    resp = requests.post('http://192.168.10.103:47101/v1/controller/methods/cooldown()')
                else:
                    resp = requests.put("http://192.168.10.103:47101/v1/controller/properties/platformTargetTemperature", json={"platformTargetTemperature": target})
                    #If the target temp is over the cutoff and the system is not cooling down, no further action is needed
        return value
 
if __name__ == '__main__':
    pass