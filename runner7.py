import os
import sys
import traci
import random
import csv

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))

sumoBinary = "C:\\Program Files (x86)\\Eclipse\\Sumo\\bin\\sumo-gui.exe"
sumoCmd = [sumoBinary, "-c", "C:\\Users\\Lenovo\\Desktop\\Sumo 3.1\\gothamcity.sumocfg"]
traci.start(sumoCmd)

csv_file_path = 'vehicle_charge_levels_8.csv'
station_capacity_csv_path = 'station_capacity.csv'
log_file_path = 'simulation_log.txt'
log2_file_path = "station_capacity_updated.txt"

def write_to_csv(data, filename):
    with open(filename, mode='+a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:  # If the file is empty
            writer.writerow(['Step', 'Vehicle_ID', 'Charge'])
        writer.writerows(data)

def log_to_file(message, filename):
    with open(filename, mode='+a', newline='') as file:
        file.write(message + '\n')

def getDistance(vehID, stationID):   
    carPosition = traci.vehicle.getLanePosition(vehID)
    carLane = traci.vehicle.getLaneID(vehID)
    carEdge = traci.lane.getEdgeID(carLane)
    startPos = traci.chargingstation.getStartPos(stationID)
    stationLane = traci.chargingstation.getLaneID(stationID)
    stationEdge = traci.lane.getEdgeID(stationLane)
    distance = traci.simulation.getDistanceRoad(carEdge, carPosition, stationEdge, startPos, isDriving=True)
    return distance

def findStation(vehID):
    stationList = traci.chargingstation.getIDList()
    stationWithDistance = {}
    for station in stationList:
        distance = getDistance(vehID, station)
        if distance > 0:
            stationWithDistance[station] = distance      
    sortedStations = sorted(stationWithDistance.items(), key=lambda x: x[1])
    for item in sortedStations:
        sortedStation = item[0]
        if isAvailable(sortedStation):
            return sortedStation
    return sortedStations[0][0]

stationWithCapacity = {}
def initializeStations():
    stationList = traci.chargingstation.getIDList()
    for station in stationList:
        stationWithCapacity[station] = 0

def isAvailable(stationID):
    if stationID in stationWithCapacity and stationWithCapacity[stationID] <= 1:
        stationWithCapacity[stationID] += 1
        log_to_file(f"Step: {step} Station Capacity Increased : {stationWithCapacity}", log2_file_path)
        return True
    return False 

def writeCapacityToFile(filename, step):
    with open(filename, mode='+a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:  # If the file is empty
            writer.writerow(['Step', 'Station_ID', 'Capacity'])
        for station, capacity in stationWithCapacity.items():
            writer.writerow([step, station, capacity])

def updateCapacity(vehID):
    chargingStations = traci.chargingstation.getIDList()
    for station in chargingStations:
        vehicles = traci.chargingstation.getVehicleIDs(station)
        for vehicle in vehicles:
            if vehicle == vehID:
                stationWithCapacity[station] -= 1
                log_to_file(f"Step: {step} Station Capacity Decreased: {stationWithCapacity}", log2_file_path)

def reroute(vehID):
    stationID = findStation(vehID)
    stationLane = traci.chargingstation.getLaneID(stationID)
    stationEdge = traci.lane.getEdgeID(stationLane)
    traci.vehicle.changeTarget(vehID, stationEdge)
    traci.vehicle.setChargingStationStop(vehID, stationID)
    return stationID

def createTraffic(vehicleNum):
    traci.route.add(routeID="r_0", edges=["-E31", "E34"])
    for i in range(vehicleNum):
        batteryCharge = random.randint(39, 99)
        traci.vehicle.add(vehID=str(i), routeID="r_0", depart=i * 20)
        traci.vehicle.setParameter(str(i), "my_vehicle.battery.charge.level", batteryCharge)
        traci.vehicle.setParameter(str(i), "has.battery.device", "true")

def batterySimulation(step):
    vehicles = traci.vehicle.getIDList()
    for vehicle in vehicles:
        carLane = traci.vehicle.getLaneID(vehicle)
        carEdge = traci.lane.getEdgeID(carLane) 
        chargelevel = int(traci.vehicle.getParameter(vehicle, "my_vehicle.battery.charge.level"))
        charge_data = [[step, vehicle, chargelevel]]  # Data to be written to CSV
        
        if carEdge == "E34" and chargelevel > 30:
            traci.vehicle.changeTarget(vehicle, "E31")
        elif carEdge == "E31" and chargelevel > 30:
            traci.vehicle.changeTarget(vehicle, "E34")
           
        write_to_csv(charge_data, csv_file_path)
                   
        if chargelevel <= 100:
            if traci.vehicle.isStopped(vehicle):
                traci.vehicle.setParameter(vehicle, "my_vehicle.battery.charge.level", chargelevel + 1)
                log_to_file(f"Vehicle {vehicle} is charging", log_file_path)  # şarj oluyor
            else:
                traci.vehicle.setParameter(vehicle, "my_vehicle.battery.charge.level", chargelevel - 1)
        if chargelevel == 30:
            if not traci.vehicle.isStopped(vehicle):
                stationID = reroute(vehicle)
                log_to_file(f"Vehicle {vehicle} rerouted to station {stationID}. Number of vehicles directed to station: {stationWithCapacity[stationID]}. Step: {step}", log_file_path)
        
        if chargelevel == 80 and traci.vehicle.isStopped(vehicle):
            updateCapacity(vehicle)
            traci.vehicle.resume(vehicle)
            log_to_file(f"Vehicle {vehicle} has charged completely", log_file_path)  ## şarj oldu
            stationID = reroute(vehicle)
        
        #if chargelevel == 0:
            #log_to_file(f"{vehicle} stay on track", log_file_path)

    writeCapacityToFile(station_capacity_csv_path, step)

step = 0

while step < 2:
    traci.simulationStep()
    step += 1

initializeStations()
createTraffic(20)

while step < 1000:
    traci.simulationStep()
    if(step % 2 == 0):
        batterySimulation(step)
    step += 1

traci.close()
