#!/usr/bin/env python
# -*- coding: utf-8 -*-

# satprep_prepare_maintenance.py - a script for (un)scheduling
# downtimes for hosts monitored by Nagios/Icinga/Thruk/Shinken
# and creating/removing VM snapshots using libvirt
#
# 2015 By Christian Stankowic
# <info at stankowic hyphen development dot net>
# https://github.com/stdevel
#

import logging
import sys
from optparse import OptionParser
from optparse import OptionGroup
import csv
from satprep_shared import schedule_downtime, get_credentials

#set logger
LOGGER = logging.getLogger('satprep_prepare_maintenance')
downtimeHosts=[]
snapshotHosts=[]

#NOTES
#



def setDowntimes():
	#stop if no hosts affected
	if len(snapshotHosts) == 0:
		LOGGER.info("No downtimes to schedule, going home!")
		exit(0)
	
	#get monitoring credentials
	if options.dryrun == False: (monUsername, monPassword) = get_credentials("Monitoring", options.monAuthfile)
	
	#set downtime for affected hosts
	for host in downtimeHosts:
		if options.dryrun:
			#simulation
			if options.tidy and options.skipMonitoring == False:
				LOGGER.info("I'd like to unschedule downtime for host '" + host + "'...")
			elif options.tidy == False and options.skipMonitoring == False:
				LOGGER.info("I'd like to schedule downtime for host '" + host + "' for " + options.hours + " hours using the comment '" + options.comment + "'...")
		else:
			#_(un)schedule_ all the downtimes
			if options.tidy and options.skipMonitoring == False:
				LOGGER.debug("Unscheduling downtime for host '" + host + "'...")
			elif options.tidy == False and options.skipMonitoring == False:
				LOGGER.debug("Scheduling downtime for host '" + host + "' (hours=" + options.hours + ", comment=" + options.comment + ")...")
			
			#setup headers
			if len(options.userAgent) > 0:
				myHeaders = {'User-Agent': options.userAgent}
			else:
				myHeaders = {'User-Agent': 'satprep Toolkit (https://github.com/stdevel/satprep)'}
			
			#(un)schedule downtime
			result = schedule_downtime(options.URL, monUsername, monPassword, host, options.hours, options.comment, options.userAgent, options.noAuth, options.tidy)



def createSnapshots():
	#stop if no hosts affected
	if len(snapshotHosts) == 0:
		LOGGER.info("No downtimes to schedule, going home!")
		exit(0)
	
	#get virtualization credentials
	if options.dryrun == False: (virtUsername, virtPassword) = get_credentials("Virtualization", options.virtAuthfile)
	
	#set downtime for affected hosts
	for host in snapshotHosts:
		if options.dryrun:
			#simulation
			if options.tidy and options.skipSnapshot == False:
				LOGGER.info("I'd like to remove a snapshot for host '" + host + "'...")
			elif options.tidy == False and options.skipSnapshot == False:
				LOGGER.info("I'd like to create a snapshot for host '" + host + "'...")
		else:
			#_create/remove_ all the snapshots
			if options.tidy and options.skipSnapshot == False:
				LOGGER.info("Removing a snapshot for host '" + host + "'...")
			elif options.tidy == False and options.skipSnapshot == False:
				LOGGER.info("Creating a snapshot for host '" + host + "'...")
			
			#create/remove snapshot
			#TODO: virtURI and custom hostname?
			result = create_snapshot(virtURI, virtUsername, virtPassword, host, options.comment, options.tidy)



def readFile(file):
	#get affected hosts from CSV report
	global downtimeHosts
	global snapshotHosts
	#read report header and get column index for hostname ,reboot and monitoring flag (if any)
	rFile = open(args[1], 'r')
	header = rFile.readline()
	headers = header.replace("\n","").replace("\r","").split(";")
	repcols = { "hostname" : 666, "errata_reboot" : 666, "system_monitoring" : 666, "system_monitoring_name" : 666, "system_virt" : 666, "system_virt_snapshot" : 666, "system_virt_vmname" : 666 }
	for name,value in repcols.items():
		try:
			#try to find index
			repcols[name] = headers.index(name)
		except ValueError:
			LOGGER.debug("DEBUG: unable to find column index for " + name + " so I'm disabling it.")
	#print report column indexes
	LOGGER.debug("DEBUG: report column indexes: {0}".format(str(repcols)))
	
	#read report and add affected hosts
	with open(file, 'rb') as csvfile:
		filereader = csv.reader(csvfile, delimiter=';', quotechar='|')
		for row in filereader:
			#print ', '.join(row)
			if options.noIntelligence == True:
				#simply add the damned host, add custom names if defined
				if repcols["system_monitoring_name"] < 666 and row[repcols["system_monitoring_name"]] != "": downtimeHosts.append(row[repcols["system_monitoring_name"]])
				else: downtimeHosts.append(row[repcols["hostname"]])
				if repcols["system_virt_vmname"] < 666 and row[repcols["system_virt_vmname"]] != "": snapshotHosts.append(row[repcols["system_virt_vmname"]])
				else: snapshotHosts.append(row[repcols["hostname"]])
			else:
				#add host to downtimeHosts if reboot required and monitoring flag set, add custom names if defined
				if repcols["system_monitoring"] < 666 and row[repcols["system_monitoring"]] == "1" and repcols["errata_reboot"] < 666 and row[repcols["errata_reboot"]] == "1":
					if repcols["system_monitoring_name"] < 666 and row[repcols["system_monitoring_name"]] != "": downtimeHosts.append(row[repcols["system_monitoring_name"]])
					else: downtimeHosts.append(row[repcols["hostname"]])
				#add host to snapshotHosts if virtual and snapshot flag set
				if repcols["system_virt"] < 666 and row[repcols["system_virt"]] == "1" and repcols["system_virt_snapshot"] < 666 and row[repcols["system_virt_snapshot"]] == "1":
					if repcols["system_virt_vmname"] < 666 and row[repcols["system_virt_vmname"]] != "": snapshotHosts.append(row[repcols["system_virt_vmname"]])
					else: snapshotHosts.append(row[repcols["hostname"]])
					
	#remove duplicates and 'hostname' line
	downtimeHosts = sorted(set(downtimeHosts))
	snapshotHosts = sorted(set(snapshotHosts))
	if "hostname" in downtimeHosts: downtimeHosts.remove("hostname")
	if "hostname" in snapshotHosts: snapshotHosts.remove("hostname")
	#print affected hosts
	LOGGER.debug("DEBUG: affected hosts for downtimes: {0}".format(downtimeHosts))
	LOGGER.debug("DEBUG: affected hosts for snapshots: {0}".format(snapshotHosts))



def main(options):
	#read file and schedule downtimes
	LOGGER.debug("Options: {0}".format(options))
	LOGGER.debug("Args: {0}".format(args))
	#read file, set downtimes and create snapshots
	readFile(args[1])
	setDowntimes()
	createSnapshots()



def parse_options(args=None):
	if args is None:
		args = sys.argv
	
	# define usage, description, version and load parser
	usage = "usage: %prog [options] snapshot.csv"
	desc = '''%prog is used to prepare maintenance for systems managed with Spacewalk, Red Hat Satellite or SUSE Manager. This includes (un)scheduling downtimes in Nagios, Icinga and Shinken and creating/removing snapshots of virtual machines. As this script uses libvirt multiple hypervisors are supported (see GitHub and libvirt documenation). Login credentials are assigned using the following shell variables:
	SATELLITE_LOGIN	username for Satellite
	SATELLITE_PASSWORD	password for Satellite
	LIBVIRT_LOGIN	username for virtualization host
	LIBVIRT_PASSWORD	password for virtualization host
	
	Alternatively you can also use auth files including a valid username (first line) and password (second line) for the monitoring and virtualization host. Make sure to use file permissions 0600 for these files.
	
	Check-out the GitHub documentation (https://github.com/stdevel/satprep) for further information.
	'''
	parser = OptionParser(usage=usage, description=desc, version="%prog version 0.3")
	#define option groups
	genOpts = OptionGroup(parser, "Generic Options")
	monOpts = OptionGroup(parser, "Monitoring Options")
	vmOpts = OptionGroup(parser, "VM Options")
	parser.add_option_group(genOpts)
	parser.add_option_group(monOpts)
	parser.add_option_group(vmOpts)
	
	#GENERIC OPTIONS
	#-c / --comment
	genOpts.add_option("-c", "--comment", action="store", dest="comment", default="System maintenance scheduled by satprep", metavar="COMMENT", help="defines a comment for downtimes and snapshots (default: 'System maintenance scheduled by satprep')")
	#-d / --debug
	genOpts.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="enable debugging outputs")
	#-f / --no-intelligence
	genOpts.add_option("-f", "--no-intelligence", dest="noIntelligence", action="store_true", default=False, help="disables checking for patches requiring reboot, simply schedules downtimes and creates snapshots for all hosts mentioned in the CSV report (default: no)")
	#-n / --dry-run
	genOpts.add_option("-n", "--dry-run", action="store_true", dest="dryrun", default=False, help="only simulates tasks that would be executed")
	#-T / --tidy
	genOpts.add_option("-T", "--tidy", dest="tidy", action="store_true", default=False, help="unschedules downtimes and removes previously created snapshots (default: no)")
	#-V / --verify-only
	vmOpts.add_option("-V", "--verify-only", dest="verify", action="store_true", default="False", help="verifies that all required downtimes and snapshots have been created and quits (default: no)")
	
	#MONITORING OPTIONS
	#-k / --skip-monitoring
	monOpts.add_option("-k", "--skip-monitoring", dest="skipMonitoring", action="store_true", default=False, help="skips creating/removing downtimes (default: no)")
	#-a / --mon-authfile
	monOpts.add_option("-a", "--mon-authfile", dest="monAuthfile", metavar="FILE", default="", help="defines an auth file to use for monitoring")
	#-u / --monitoring-url
	monOpts.add_option("-u", "--monitorung-url", dest="URL", metavar="URL", default="http://localhost/icinga", help="defines the Nagios/Icinga/Thruk/Shinken URL to use (default: http://localhost/icinga)")
	#-t / --hours
	monOpts.add_option("-t", "--hours", action="store", dest="hours", default="2", metavar="HOURS", help="sets the time period in hours hosts should be scheduled for downtime (default: 2)")
	#-x / --no-auth
	monOpts.add_option("-x", "--no-auth", action="store_true", default=False, dest="noAuth", help="disables HTTP basic auth (often used with Nagios/Icinga and OMD) (default: no)")
	#-A / --user-agent
	monOpts.add_option("-A", "--user-agent", action="store", default="", metavar="AGENT", dest="userAgent", help="sets a custom HTTP user agent")
	
	#VM OPTIONS
	#-K / --skip-snapshot
	vmOpts.add_option("-K", "--skip-snapshot", dest="skipSnapshot", action="store_true", default=False, help="skips creating/removing snapshots (default: no)")
	#-H / --libvirt-uri
	vmOpts.add_option("-H", "--libvirt-uri", dest="libvirtURI", action="store", default="", metavar="URI", help="defines the URI to virtualization host or management (use libvirt URI)")
	#-C / --virt-authfile
	vmOpts.add_option("-C", "--virt-authfile", dest="virtAuthfile", action="store", metavar="FILE", default="", help="defines an auth file to use for virtualization")
	#-X / --remove-all
	vmOpts.add_option("-X", "--remove-all", dest="removeAll", action="store_true", default=False, help="removes all snapshots during tidying up (default: no)")
	
	(options, args) = parser.parse_args(args)
	
	#check whether snapshot reported
	if len(args) != 2:
		print "ERROR: you need to specify exactly one snapshot report!"
		exit(1)
	
	#TODO: check for senseful parameters
	
	return (options, args)



if __name__ == "__main__":
	(options, args) = parse_options()
	#set logger level
	if options.debug:
		logging.basicConfig(level=logging.DEBUG)
		LOGGER.setLevel(logging.DEBUG)
	else:
		logging.basicConfig()
		LOGGER.setLevel(logging.INFO)
	main(options)
