package main

// A simple runanalyzer doing the below actions.
//
// 1. list last 3 builds abort jobs
// 2. Total duration of a build cycle
// 3. Execute a given CB N1QL query
// 4. Save the jenkins logs to S3. List of jobs can csv or CB server for a build
//
// jagadesh.munta@couchbase.com

import (
	"bufio"
	"bytes"
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"math"
	"net/http"
	"os"
	"os/exec"
	"path"
	"strconv"
	"strings"
	"time"

	"github.com/magiconair/properties"
	"gopkg.in/ini.v1"
)

// N1QLQryResult type
type N1QLQryResult struct {
	Status  string
	Results []N1QLResult
}

// N1QLResult type
type N1QLResult struct {
	Aname    string
	JURL     string
	URLbuild int64
}

// TotalCycleTimeQryResult type
type TotalCycleTimeQryResult struct {
	Status  string
	Results []TotalCycleTime
}

// TotalCycleTime type
type TotalCycleTime struct {
	Build      string
	Numofjobs  int
	Totaltime  int64
	Failcount  int
	Totalcount int
}

// CBBuildQryResult type
type CBBuildQryResult struct {
	Status  string
	Results []CBBuild
}

// CBBuild type
type CBBuild struct {
	Build string
}

// JobStatusQryResult type
type JobStatusQryResult struct {
	Status  string
	Results []JobStatus
}

// JobStatus type
type JobStatus struct {
	Result    string
	Numofjobs int
}

//const url = "http://172.23.109.245:8093/query/service"

var cbbuild string
var src string
var dest string
var overwrite string
var updateURL string
var cbplatform string
var s3bucket string
var url string
var updateOrgURL string
var includes string
var limits string
var finallimits string
var totalmachines string
var qryfilter string
var workspace string
var cbrelease string

func main() {
	fmt.Println("*** Helper Tool ***")
	action := flag.String("action", "usage", usage())
	srcInput := flag.String("src", "cbserver", usage())
	destInput := flag.String("dest", "local", usage())
	overwriteInput := flag.String("overwrite", "no", usage())
	updateURLInput := flag.String("updateurl", "no", usage())
	cbplatformInput := flag.String("os", "centos", usage())
	s3bucketInput := flag.String("s3bucket", "cb-logs-qe", usage())
	urlInput := flag.String("cbqueryurl", "http://172.23.109.245:8093/query/service", usage())
	updateOrgURLInput := flag.String("updateorgurl", "no", usage())
	includesInput := flag.String("includes", "console,config,parameters,testresult", usage())
	limitsInput := flag.String("limits", "100", usage())
	finallimitsInput := flag.String("finallimits", "100", usage())
	totalmachinesInput := flag.String("totalmachines", "false", usage())
	qryfilterInput := flag.String("qryfilter", " ", usage())
	workspaceInput := flag.String("workspace", "testrunner", usage())
	cbreleaseInput := flag.String("cbrelease", "6.5", usage())

	flag.Parse()
	dest = *destInput
	src = *srcInput
	overwrite = *overwriteInput
	updateURL = *updateURLInput
	cbplatform = *cbplatformInput
	s3bucket = *s3bucketInput
	url = *urlInput
	updateOrgURL = *updateOrgURLInput
	includes = *includesInput
	limits = *limitsInput
	finallimits = *finallimitsInput
	totalmachines = *totalmachinesInput
	qryfilter = *qryfilterInput
	workspace = *workspaceInput
	cbrelease = *cbreleaseInput

	//fmt.Println("original dest=", dest, "--", *destInput)
	//time.Sleep(10 * time.Second)
	if *action == "lastaborted" {
		lastabortedjobs()
	} else if *action == "savejoblogs" {
		savejoblogs()
	} else if *action == "totaltime" {
		//gettotalbuildcycleduration(os.Args[3])
		fmt.Printf("\n\t\t\t\t\t\t\t\t\t\t\tGrand total time: %d hours\n", gettotalbuildcycleduration(os.Args[3]))
	} else if *action == "runquery" {
		fmt.Println("Query Result: ", runquery(os.Args[3]))
	} else if *action == "usage" {
		fmt.Println(usage())
	} else {
		fmt.Println(usage())
	}
}

func usage() string {
	fileName, _ := os.Executable()
	return "Usage: " + fileName + " -h | --help \nEnter action value. \n" +
		"-action lastaborted 6.5.0-4106 6.5.0-4059 6.5.0-4000  : to get the aborted jobs common across last 3 builds. Options: --cbrelease [6.5]specificbuilds --limits 3 --qryfilter 'where numofjobs>900' \n" +
		"-action savejoblogs 6.5.0-4106  : to download the jenkins logs and save in S3 for a given build. " +
		"Options: --dest [local]|s3|none --src csvfile --os centos --overwrite [no]|yes --updateurl [no]|yes --includes [console,config,parameters,testresult],archive" +
		"--s3bucket cb-logs-qe --cbqueryurl [http://172.23.109.245:8093/query/service]\n" +
		"-action totaltime 6.5  : to get the total number of jobs, time duration for a given set of  builds in a release, " +
		"Options: --limits [100] --qryfilter 'where result.numofjobs>900 and (totalcount-failcount)*100/totalcount>90'\n" +
		"-action runquery 'select * from server where lower(`os`)=\"centos\" and `build`=\"6.5.0-4106\"' : to run a given query statement"
}
func runquery(qry string) string {
	//url := "http://172.23.109.245:8093/query/service"
	fmt.Println("ACTION: runquery")
	fmt.Println("query=" + qry)
	localFileName := "qryresult.json"
	if err := executeN1QLStmt(localFileName, url, qry); err != nil {
		panic(err)
	}

	resultFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer resultFile.Close()

	byteValue, _ := ioutil.ReadAll(resultFile)
	return string(byteValue)
}

func gettotalbuildcycleduration(buildN string) int {
	//fmt.Println("action: totaltime")

	var build1 string
	//var builds string
	if len(os.Args) < 2 {
		fmt.Println("Enter the build to get the number of jobs and total duration.")
		os.Exit(1)
	} else {
		build1 = os.Args[len(os.Args)-1]
		cbbuild = build1
		//builds = build1
	}
	var totalhours int

	// For all build releases
	/*
		builds = ""
		var cbbuildrel = strings.Split(build1, ",")
		for i := 0; i < len(cbbuildrel); i++ {
			cbbuild = cbbuildrel[i]
			// get build ids
			qry1 := "select distinct `build` from server where lower(os)like \"" + cbplatform + "\" and `build` like \"" + cbbuild + "%\"  order by `build` desc limit " + limits
			localFileName1 := "cbbuilds.json"
			if err1 := executeN1QLStmt(localFileName1, url, qry1); err1 != nil {
				panic(err1)
			}

			resultFile1, err1 := os.Open(localFileName1)
			if err1 != nil {
				fmt.Println(err1)
			}
			defer resultFile1.Close()

			byteValue1, _ := ioutil.ReadAll(resultFile1)

			var result1 CBBuildQryResult

			err1 = json.Unmarshal(byteValue1, &result1)
			if result1.Status == "success" {

				for i := 0; i < len(result1.Results); i++ {
					builds += result1.Results[i].Build
					if i < len(result1.Results)-1 {
						builds += ","
					}
					//fmt.Printf("buildid=%s, builds=%s", result1.Results[i].Build, builds)

				}
			}

		}
	*/
	// total jobs
	//var cbbuilds = strings.Split(builds, ",")
	outFile, _ := os.Create("totaltime_summary.txt")
	outW := bufio.NewWriter(outFile)
	defer outFile.Close()

	fmt.Printf("\nSummary report of regression cycles on the last %s build(s) in %s %s\n", limits, cbbuild, qryfilter)
	fmt.Fprintf(outW, "\nSummary report of regression cycles on the last %s build(s) in %s %s\n", limits, cbbuild, qryfilter)

	if totalmachines == "true" {
		fmt.Println("---------------------------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Println("S.No.\tBuild\t\tTestCount\tPassedCount\tFailedCount\tPassrate\tJobcount(A,F,U,S)\tTotaltime\t\t\t\tMachinesCount")
		fmt.Println("---------------------------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Fprintln(outW, "---------------------------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Fprintln(outW, "S.No.\tBuild\t\tTestCount\tPassedCount\tFailedCount\tPassrate\tJobscount(A,F,U,S)\tTotaltime\t\t\t\tMachinesCount")
		fmt.Fprintln(outW, "---------------------------------------------------------------------------------------------------------------------------------------------------------------------")
	} else {
		fmt.Println("-----------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Println("S.No.\tBuild\t\tTestCount\tPassedCount\tFailedCount\tPassrate\tJobcount(A,F,U,S)\tTotaltime")
		fmt.Println("-----------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Fprintln(outW, "-----------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Fprintln(outW, "S.No.\tBuild\t\tTestCount\tPassedCount\tFailedCount\tPassrate\tJobscount(A,F,U,S)\tTotaltime")
		fmt.Fprintln(outW, "-----------------------------------------------------------------------------------------------------------------------------------------------------")
	}

	sno := 1
	//for i := 0; i < len(cbbuilds); i++ {
	//	cbbuild = cbbuilds[i]

	//url := "http://172.23.109.245:8093/query/service"
	//qry := "select count(*) as numofjobs, sum(duration) as totaltime, sum(failCount) as failcount, sum(totalCount) as totalcount from server b where lower(b.os) like \"" + cbplatform + "\" and b.`build`=\"" + cbbuild + "\" " + qryfilter
	//qry := "select numofjobs, totaltime, failcount, totalcount from (select count(*) as numofjobs, sum(duration) as totaltime, sum(failCount) as failcount, sum(totalCount) as totalcount from server b " +
	//	"where lower(b.os) like \"" + cbplatform + "\" and b.`build`=\"" + cbbuild + "\" ) as result " + qryfilter + " limit " + finallimits
	qry := "select `build`, numofjobs, totaltime, failcount, totalcount from (select b.`build`, count(*) as numofjobs, sum(duration) as totaltime, sum(failCount) as failcount, sum(totalCount) as totalcount from server b " +
		"where lower(b.os) like \"" + cbplatform + "\" and b.`build` like \"" + cbbuild + "%\" group by b.`build` order by b.`build` desc) as result " + qryfilter + " limit " + limits
	//qry := "select `build`, numofjobs, totaltime, failcount, totalcount from (select b.`build`, count(*) as numofjobs, sum(duration) as totaltime, sum(failCount) as failcount, sum(totalCount) as totalcount from server b where lower(b.os) like "centos" and b.`build` like "6.5%" group by b.`build` order by b.`build` desc) as result where numofjobs>500 limit 30"
	//fmt.Println("\nquery=" + qry)
	localFileName := "duration.json"
	if err := executeN1QLStmt(localFileName, url, qry); err != nil {
		//panic(err)
		log.Println(err)
	}
	resultFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer resultFile.Close()

	byteValue, _ := ioutil.ReadAll(resultFile)

	var result TotalCycleTimeQryResult

	err = json.Unmarshal(byteValue, &result)

	//if len(result.Results) < 1 {
	//	continue
	//}
	if result.Status == "success" {
		//fmt.Println(" Total time in millis: ", result.Results[0].Totaltime)

		for i := 0; i < len(result.Results); i++ {
			cbbuild = result.Results[i].Build

			// get jobs status
			abortedJobs, failureJobs, unstableJobs, successJobs := getJobsStatusList(cbbuild)

			hours := math.Floor(float64(result.Results[i].Totaltime) / 1000 / 60 / 60)
			totalhours += int(hours)
			secs := result.Results[i].Totaltime % (1000 * 60 * 60)
			mins := math.Floor(float64(secs) / 60 / 1000)
			//secs = result.Results[i].Totaltime * 1000 % 60
			passCount := result.Results[i].Totalcount - result.Results[i].Failcount

			fmt.Printf("\n%3d.\t%s\t%5d\t\t%5d\t\t%5d\t\t%6.2f%%\t\t%3d(%3d,%3d,%3d,%3d)\t%4d hrs %2d mins (%11d millis)",
				(sno), cbbuild, result.Results[i].Totalcount, passCount, result.Results[i].Failcount,
				(float32(passCount)/float32(result.Results[i].Totalcount))*100, result.Results[i].Numofjobs, abortedJobs, failureJobs, unstableJobs, successJobs, int64(hours), int64(mins), result.Results[i].Totaltime)
			fmt.Fprintf(outW, "\n%3d.\t%s\t%5d\t\t%5d\t\t%5d\t\t%6.2f%%\t\t%3d(%3d,%3d,%3d,%3d)\t%4d hrs %2d mins (%11d millis)",
				(sno), cbbuild, result.Results[i].Totalcount, passCount, result.Results[i].Failcount,
				(float32(passCount)/float32(result.Results[i].Totalcount))*100, result.Results[i].Numofjobs, abortedJobs, failureJobs, unstableJobs, successJobs, int64(hours), int64(mins), result.Results[i].Totaltime)

			//get machines list
			totalMachinesCount := 0
			if totalmachines == "true" {
				totalMachinesCount = getMachinesList(cbbuild)
				if totalMachinesCount != 0 {
					fmt.Printf("\t%4d", totalMachinesCount)
					fmt.Fprintf(outW, "\t%4d", totalMachinesCount)
				}
			}

			sno++
			//fmt.Printf("\n%d. %s, Number of jobs=%d, Total duration=%02d hrs %02d mins (%02d millis)", i, cbbuild, result.Results[0].Numofjobs, int64(hours), int64(mins), result.Results[0].Totaltime)
			//fmt.Printf("Number of jobs=%d, Total duration=%02d hrs : %02d mins :%02d secs", result.Results[0].Numofjobs, int64(hours), int64(mins), int64(secs))
			//ttime = string(hours) + ": " + string(mins) + ": " + string(secs)
			outW.Flush()
		}
	} else {
		fmt.Println("Status: Failed. " + err.Error())
	}
	//}
	if totalmachines == "true" {
		fmt.Println("\n---------------------------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Fprintln(outW, "\n---------------------------------------------------------------------------------------------------------------------------------------------------------------------")
	} else {
		fmt.Println("\n-----------------------------------------------------------------------------------------------------------------------------------------------------")
		fmt.Fprintln(outW, "\n-----------------------------------------------------------------------------------------------------------------------------------------------------")
	}
	p := fmt.Println
	t := time.Now()
	p(t.Format(time.RFC3339))
	fmt.Fprintf(outW, "\n%s\t\t\t\t\t\t\t\t\t\tGrand total time=%6d hours\n", t.Format(time.RFC3339), totalhours)

	outW.Flush()

	return totalhours

}

func savejoblogs() {
	fmt.Println("action: savejoblogs")
	var build1 string
	if len(os.Args) < 2 {
		fmt.Println("Enter the build to save the jenkins job logs.")
		os.Exit(1)
	} else {
		build1 = os.Args[len(os.Args)-1]
		cbbuild = build1
	}
	var jobCsvFile string
	if src == "cbserver" {
		//url := "http://172.23.109.245:8093/query/service"
		qry := "select b.name as aname,b.url as jurl,b.build_id urlbuild from server b where lower(b.os) like \"" + cbplatform + "\" and b.`build`=\"" + build1 + "\""
		fmt.Println("query=" + qry)
		localFileName := "result.json"
		if err := executeN1QLStmt(localFileName, url, qry); err != nil {
			panic(err)
		}

		resultFile, err := os.Open(localFileName)
		if err != nil {
			fmt.Println(err)
		}
		defer resultFile.Close()

		byteValue, _ := ioutil.ReadAll(resultFile)

		var result N1QLQryResult

		err = json.Unmarshal(byteValue, &result)
		//fmt.Println("Status=" + result.Status)
		//fmt.Println(err)
		jobCsvFile = cbbuild + "_all_jobs.csv"
		f, err := os.Create(jobCsvFile)
		defer f.Close()

		w := bufio.NewWriter(f)

		if result.Status == "success" {
			fmt.Println("Count: ", len(result.Results))
			for i := 0; i < len(result.Results); i++ {
				//fmt.Println((i + 1), result.Results[i].Aname, result.Results[i].JURL, result.Results[i].URLbuild)
				fmt.Print(strings.TrimSpace(result.Results[i].Aname), ",", strings.TrimSpace(result.Results[i].JURL), ",",
					result.Results[i].URLbuild, "\n")
				_, err = fmt.Fprintf(w, "%s,%s,%d\n", strings.TrimSpace(result.Results[i].Aname), strings.TrimSpace(result.Results[i].JURL),
					result.Results[i].URLbuild)
			}
			w.Flush()
			fmt.Println("Count: ", len(result.Results))

		} else {
			fmt.Println("Status: Failed")
		}
	} else {
		jobCsvFile = src
	}

	// Download the files
	if !strings.Contains(strings.ToLower(dest), "none") {
		DownloadJenkinsFiles(jobCsvFile)
	}

}

// getJobsList of a given build
func getJobsList(build1 string) string {

	var jobCsvFile string
	if src == "cbserver" {
		//url := "http://172.23.109.245:8093/query/service"
		qry := "select b.name as aname,b.url as jurl,b.build_id urlbuild from server b where lower(b.os) like \"" + cbplatform + "\" and b.`build`=\"" + build1 + "\""
		//fmt.Println("query=" + qry)
		localFileName := "jobslistresult.json"
		if err := executeN1QLStmt(localFileName, url, qry); err != nil {
			panic(err)
		}

		resultFile, err := os.Open(localFileName)
		if err != nil {
			fmt.Println(err)
		}
		defer resultFile.Close()

		byteValue, _ := ioutil.ReadAll(resultFile)

		var result N1QLQryResult

		err = json.Unmarshal(byteValue, &result)
		//fmt.Println("Status=" + result.Status)
		//fmt.Println(err)
		jobCsvFile = build1 + "_all_jobs.csv"
		f, err := os.Create(jobCsvFile)
		defer f.Close()

		w := bufio.NewWriter(f)

		if result.Status == "success" {
			fmt.Printf(" Jobs Count: %d\n", len(result.Results))
			for i := 0; i < len(result.Results); i++ {
				//fmt.Println((i + 1), result.Results[i].Aname, result.Results[i].JURL, result.Results[i].URLbuild)
				//fmt.Print(strings.TrimSpace(result.Results[i].Aname), ",", strings.TrimSpace(strings.ReplaceAll(result.Results[i].JURL, "=", "")), ",",
				//	result.Results[i].URLbuild, "\n")
				_, err = fmt.Fprintf(w, "%s,%s,%d\n", strings.TrimSpace(result.Results[i].Aname), strings.TrimSpace(strings.ReplaceAll(result.Results[i].JURL, ",", "")),
					result.Results[i].URLbuild)
				if err != nil {
					log.Println(err)
				}
			}
			w.Flush()
			f.Close()
			//fmt.Println("Count: ", len(result.Results))
			resultFile.Close()
		} else {
			fmt.Println("Status: Failed")
		}
	} else {
		jobCsvFile = src
	}

	return jobCsvFile
}

// getMachinesList...
func getMachinesList(build1 string) int {
	fmt.Printf("\n-->Build: %s ", build1)
	var jobCsvFile = getJobsList(build1)
	// Download the files
	includes = "console,parameters"
	dest = "local"
	return DownloadJenkinsJobInfo(jobCsvFile)
	// Parse the properties file

}

// getJobsStatusList of a given build
func getJobsStatusList(build1 string) (int, int, int, int) {

	abortedJobs := 0
	failureJobs := 0
	unstableJobs := 0
	successJobs := 0
	if src == "cbserver" {
		//url := "http://172.23.109.245:8093/query/service"
		//qry := "select b.name as aname,b.url as jurl,b.build_id urlbuild from server b where lower(b.os) like \"" + cbplatform + "\" and b.`build`=\"" + build1 + "\""
		qry := "select result, count(*) as numofjobs from server where lower(os) like \"" + cbplatform + "\"  and `build`=\"" + build1 + "\" group by result"
		//fmt.Println("query=" + qry)
		localFileName := "jobstatusresult.json"
		if err := executeN1QLStmt(localFileName, url, qry); err != nil {
			panic(err)
		}

		resultFile, err := os.Open(localFileName)
		if err != nil {
			fmt.Println(err)
		}
		defer resultFile.Close()

		byteValue, _ := ioutil.ReadAll(resultFile)

		var result JobStatusQryResult

		err = json.Unmarshal(byteValue, &result)

		if result.Status == "success" {
			for i := 0; i < len(result.Results); i++ {
				switch result.Results[i].Result {
				case "ABORTED":
					abortedJobs = result.Results[i].Numofjobs
					break
				case "FAILURE":
					failureJobs = result.Results[i].Numofjobs
					break
				case "UNSTABLE":
					unstableJobs = result.Results[i].Numofjobs
					break
				case "SUCCESS":
					successJobs = result.Results[i].Numofjobs
					break
				}
			}
			resultFile.Close()
		} else {
			fmt.Println("Status: Failed")
		}
	}

	return abortedJobs, failureJobs, unstableJobs, successJobs
}

// DownloadJenkinsJobInfo ...
func DownloadJenkinsJobInfo(csvFile string) int {

	props := properties.MustLoadFile("${HOME}/.jenkins_env.properties", properties.UTF8)
	//jenkinsServer := props.MustGetString("QA_JENKINS_SERVER")
	//jenkinsUser := props.MustGetString("QA_JENKINS_USER")
	//jenkinsUserPwd := props.MustGetString("QA_JENKINS_TOKEN")

	lines, err := ReadCsv(csvFile)
	if err != nil {
		log.Println(err)
		return -1
	}
	index := 0
	numServers := 0
	totalMachines := 0
	machinesOut, machinesErr := os.Create(cbbuild + "_" + cbplatform + "_jobsmachineslist.txt")
	if machinesErr != nil {
		log.Println("Machines list file creation error ", err)
	}
	defer machinesOut.Close()
	listOut := bufio.NewWriter(machinesOut)
	for _, line := range lines {
		data := CSVJob{
			TestName: line[0],
			JobURL:   line[1],
			BuildID:  line[2],
		}
		index++
		//fmt.Println("\n" + strconv.Itoa(index) + "/" + strconv.Itoa(len(lines)) + ". " + data.TestName + " " + data.JobURL + " " + data.BuildID)
		fmt.Printf(".")

		// Start downloading
		req, _ := http.NewRequest("GET", data.JobURL, nil)
		JobName := path.Base(req.URL.Path)
		if JobName == data.BuildID {
			JobName = path.Base(req.URL.Path + "/..")
			data.JobURL = data.JobURL + "../"
		}

		JobDir := cbbuild + "/" + "jenkins_logs" + "/" + JobName + "/" + data.BuildID
		err := os.MkdirAll(JobDir, 0755)
		if err != nil {
			fmt.Println(err)
		}

		ConfigFile := JobDir + "/" + "config.xml"
		JobFile := JobDir + "/" + "jobinfo.json"
		ResultFile := JobDir + "/" + "testresult.json"
		LogFile := JobDir + "/" + "consoleText.txt"
		ArchiveZipFile := JobDir + "/" + "archive.zip"

		URLParts := strings.Split(data.JobURL, "/")
		jenkinsServer := strings.ToUpper(strings.Split(URLParts[2], ".")[0])

		if strings.Contains(strings.ToLower(jenkinsServer), s3bucket) { // from S3
			log.Println("Download from S3...")
			includedFiles := strings.Split(includes, ",")
			for i := 0; i < len(includedFiles); i++ {
				switch strings.ToLower(strings.TrimSpace(includedFiles[i])) {
				case "console":
					//log.Println("...downloading console file")
					DownloadFile(LogFile, data.JobURL+data.BuildID+"/consoleText.txt")
					break
				case "config":
					//log.Println("...downloading config file")
					DownloadFile(ConfigFile, data.JobURL+"/config.xml")
					break
				case "parameters":
					//log.Println("...downloading parameters file")
					DownloadFile(JobFile, data.JobURL+data.BuildID+"/jobinfo.json")
					break
				case "testresult":
					//log.Println("...downloading testresult file")
					DownloadFile(ResultFile, data.JobURL+data.BuildID+"/testresult.json")
					break
				case "archive":
					//log.Println("...downloading archive file")
					DownloadFile(ArchiveZipFile, data.JobURL+data.BuildID+"/archive.zip")
					break
				}
			}

		} else { // from Jenkins
			//fmt.Println("Jenkins Server: ", jenkinsServer)
			jenkinsUser := props.MustGetString(jenkinsServer + "_JENKINS_USER")
			jenkinsUserPwd := props.MustGetString(jenkinsServer + "_JENKINS_TOKEN")

			includedFiles := strings.Split(includes, ",")
			for i := 0; i < len(includedFiles); i++ {
				switch strings.ToLower(strings.TrimSpace(includedFiles[i])) {
				case "console":
					//log.Println("...downloading console file")
					if !fileExists(LogFile) {
						DownloadFileWithBasicAuth(LogFile, data.JobURL+data.BuildID+"/consoleText", jenkinsUser, jenkinsUserPwd)
					} /*else {
						log.Println("File already existed locally...")
					}*/
					substring := ""
					if fileExists(LogFile) {
						//check if log is available
						//log.Println("SearchingFile2 for No such file string...")
						substring = "No such file:"
						out, _ := SearchFile2(LogFile, substring)
						//log.Println("out=", out, "error=", err)
						if out != "" {
							//log.Println("Jenkins log is not available. Let us check at S3...")
							s3consolelogurl := "http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/" + cbbuild + "/jenkins_logs/" + JobName + "/" + data.BuildID + "/consoleText.txt"
							//log.Println("Downloading from " + s3consolelogurl)
							DownloadFile(LogFile, s3consolelogurl)
							if !fileExists(LogFile) {
								//log.Println("No log file at S3 also! skipping." + s3consolelogurl)
								continue
							} else {
								//log.Println("SearchingFile for 404...")
								out, err = SearchFile2(LogFile, "404 Not Found")
								if out != "" {
									log.Println("No log file at S3 also! skipping." + s3consolelogurl)
									break
								}
							}

						} /*else {
							log.Println("Using the local file...")
						}*/
						//log.Println("Searching for INI file...")
						substring = "testrunner -i"
						out, err = SearchFile2(LogFile, substring)
						//log.Println(out, err)

						if out == "" {
							substring = "testrunner.py -i"
							out, err = SearchFile2(LogFile, substring)
							//log.Println(out, err)
						}
						if out != "" {
							lineindex := strings.Index(out, substring)
							substring1 := out[lineindex+len(substring):]
							//log.Println(substring1)
							words := strings.Split(substring1, " ")
							numServers = 0
							if len(words) > 0 {

								iniFile := words[1]
								//log.Println("iniFile=", iniFile)
								if strings.Contains(iniFile, "/tmp") {
									out, _ := SearchFileNextLines2(LogFile, "[servers]")
									//log.Println(out, err)
									numServers = len(strings.Split(out, "\n")) - 1
								} else {
									if _, err := os.Stat(workspace); os.IsNotExist(err) {
										log.Println("The testrunner workspace directory doesn't exist. Performing git clone http://github.com/couchbase/testrunner")
										out, err := exec.Command("git", "clone", "http://github.com/couchbase/testrunner").Output()
										if err != nil {
											log.Fatal(err)
										} else {
											log.Println(out)
										}

									}

									cfg, err := ini.Load(workspace + "/" + iniFile)
									if err != nil {
										fmt.Printf("Fail to read file: %v", err)
										continue
									}

									// Classic read of values, default section can be represented as empty string
									numServers = len(cfg.Section("servers").Keys())
								}
								//fmt.Println("servers:", numServers)
								totalMachines += numServers
								//fmt.Println("Total machines:", totalMachines)
								fmt.Fprintln(listOut, "\n"+strconv.Itoa(index)+"/"+strconv.Itoa(len(lines))+". "+data.TestName+" "+data.JobURL+" "+data.BuildID+"\t"+strconv.Itoa(numServers)+"\t-->"+strconv.Itoa(totalMachines))
								listOut.Flush()
							}
						}

					}
					break
				case "config":
					//log.Println("...downloading config file")
					DownloadFileWithBasicAuth(ConfigFile, data.JobURL+"/config.xml", jenkinsUser, jenkinsUserPwd)
					break
				case "parameters":
					//log.Println("...downloading parameters file")
					DownloadFileWithBasicAuth(JobFile, data.JobURL+data.BuildID+"/api/json?pretty=true", jenkinsUser, jenkinsUserPwd)
					break
				case "testresult":
					//log.Println("...downloading testresult file")
					DownloadFileWithBasicAuth(ResultFile, data.JobURL+data.BuildID+"/testReport/api/json?pretty=true", jenkinsUser, jenkinsUserPwd)
					break
				case "archive":
					//log.Println("...downloading archive file")
					DownloadFileWithBasicAuth(ArchiveZipFile, data.JobURL+data.BuildID+"/artifact/*zip*/archive.zip", jenkinsUser, jenkinsUserPwd)
					break
				}
			}
		}
	}
	machinesOut.Close()

	return totalMachines
}

// executeCommand ...
func executeCommand(command string, input string) string {
	cmdFileWithArgs := strings.Split(command, " ")
	cmdFile := cmdFileWithArgs[0]
	cmdArgs := cmdFileWithArgs[1:]
	cmd := exec.Command(cmdFile, cmdArgs...)
	cmd.Stdin = strings.NewReader(input)
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		//log.Fatal(err)
		if out.String() != "" {
			log.Println(err)
		}
	}
	return out.String()
}

func lastabortedjobs() {
	fmt.Println("action: lastaborted")

	var build1 string
	var build2 string
	var build3 string
	var qry string
	if cbrelease == "specificbuilds" {
		build1 = os.Args[len(os.Args)-3]
		build2 = os.Args[len(os.Args)-2]
		build3 = os.Args[len(os.Args)-1]
		cbbuild = build1
		qry = "select b.name as aname,b.url as jurl,b.build_id urlbuild from server b where lower(b.os) like \"" + cbplatform + "\" and b.result=\"ABORTED\" and b.`build`=\"" +
			build1 + "\" and b.name in (select raw a.name from server a where lower(a.os) like \"" + cbplatform + "\" and a.result=\"ABORTED\" and a.`build`=\"" +
			build2 + "\" intersect select raw name from server where lower(os) like \"" + cbplatform + "\" and result=\"ABORTED\" and `build`=\"" +
			build3 + "\" intersect select raw name from server where lower(os) like \"" + cbplatform + "\" and result=\"ABORTED\" and `build`=\"" + build1 + "\")"
	} else {
		// Get latest builds
		log.Println("Finding latest builds ")
		cbbuilds := getLatestBuilds(cbrelease)
		if len(cbbuilds) < 1 {
			fmt.Println("No builds found!")
			return
		}
		var qryString = ""
		fmt.Printf("Builds: ")
		for i := 0; i < len(cbbuilds); i++ {
			fmt.Printf(cbbuilds[i].Build + " ")
			qryString += "select raw a.name from server a where lower(a.os) like \"" + cbplatform + "\" and a.result=\"ABORTED\" and a.`build`=\"" + cbbuilds[i].Build + "\""
			if i < len(cbbuilds)-1 {
				qryString += " intersect "
			}
		}
		qry = "select b.name as aname,b.url as jurl,b.build_id urlbuild from server b where lower(b.os) like \"" + cbplatform + "\" and b.result=\"ABORTED\" and b.`build`=\"" +
			cbbuilds[0].Build + "\" and b.name in (" + qryString + " )"
		fmt.Println("\nquery=" + qry)
	}

	localFileName := "abortedresult.json"
	if err := executeN1QLStmt(localFileName, url, qry); err != nil {
		panic(err)
	}

	resultFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer resultFile.Close()

	byteValue, _ := ioutil.ReadAll(resultFile)

	var result N1QLQryResult

	err = json.Unmarshal(byteValue, &result)
	//fmt.Println("Status=" + result.Status)
	//fmt.Println(err)
	f, err := os.Create("aborted_jobs.csv")
	defer f.Close()

	w := bufio.NewWriter(f)
	if result.Status == "success" {
		fmt.Println("Count: ", len(result.Results))
		for i := 0; i < len(result.Results); i++ {
			//fmt.Println((i + 1), result.Results[i].Aname, result.Results[i].JURL, result.Results[i].URLbuild)
			fmt.Printf("\n%s\t%s\t%d", result.Results[i].Aname, result.Results[i].JURL, result.Results[i].URLbuild)
			_, err = fmt.Fprintf(w, "%s,%s,%d\n", strings.TrimSpace(result.Results[i].Aname), strings.TrimSpace(result.Results[i].JURL),
				result.Results[i].URLbuild)
		}
		fmt.Println("")
		w.Flush()

	} else {
		fmt.Println("Status: Failed")
	}
}

// DownloadFile2 will download the given url to the given file.
func executeN1QLStmt(localFilePath string, remoteURL string, statement string) error {

	req, err := http.NewRequest("GET", remoteURL, nil)
	if err != nil {
		return err
	}
	urlq := req.URL.Query()
	urlq.Add("statement", statement)
	req.URL.RawQuery = urlq.Encode()
	u := req.URL.String()
	//fmt.Println(req.URL.String())
	resp, err := http.Get(u)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if localFilePath != "" {
		out, err := os.Create(localFilePath)
		if err != nil {
			return err
		}
		_, err = io.Copy(out, resp.Body)
		resp.Body.Close()
		return err
	} else {
		body, err := ioutil.ReadAll(resp.Body)
		log.Println(string(body))
		resp.Body.Close()
		return err
	}

}

func getLatestBuilds(cbrelease string) []TotalCycleTime {
	// get last limits number of builds
	qry := "select `build`, numofjobs, totaltime, failcount, totalcount from (select b.`build`, count(*) as numofjobs, sum(duration) as totaltime, sum(failCount) as failcount, sum(totalCount) as totalcount from server b " +
		"where lower(b.os) like \"" + cbplatform + "\" and b.`build` like \"" + cbrelease + "%\" group by b.`build` order by b.`build` desc) as result " + qryfilter + " limit " + limits
	//fmt.Println("\nquery=" + qry)
	localFileName := cbrelease + "_lastbuilds.json"
	if err := executeN1QLStmt(localFileName, url, qry); err != nil {
		//panic(err)
		log.Println(err)
	}
	resultFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer resultFile.Close()

	byteValue, _ := ioutil.ReadAll(resultFile)

	var result TotalCycleTimeQryResult

	err = json.Unmarshal(byteValue, &result)

	return result.Results
}

// DownloadFile2 will download the given url to the given file.
func executeN1QLPostStmt(remoteURL string, statement string) error {

	stmtStr := "{\"statement\": \"" + statement + "\"}"
	fmt.Println(stmtStr)
	var jsonStr = []byte(stmtStr)
	req, err := http.NewRequest("POST", remoteURL, bytes.NewBuffer(jsonStr))
	req.Header.Set("Content-Type", "application/json")
	//fmt.Println(req.URL.String())
	//fmt.Println(jsonStr)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	log.Println("Response= " + string(body))
	return err
}

// DownloadFile will download the given url to the given file.
func DownloadFile(localFilePath string, remoteURL string) error {
	resp, err := http.Get(remoteURL)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	out, err := os.Create(localFilePath)
	if err != nil {
		return err
	}
	_, err = io.Copy(out, resp.Body)
	out.Close()
	return err
}

// DownloadFileWithBasicAuth will download the given url to the given file.
func DownloadFileWithBasicAuth(localFilePath string, remoteURL string, userName string, pwd string) error {
	//fmt.Println("Downloading ...", localFilePath, "--", remoteURL, "---", userName, "---", pwd)
	client := &http.Client{}
	req, _ := http.NewRequest("GET", remoteURL, nil)
	//localFilePath := path.Base(req.URL.Path)
	req.SetBasicAuth(userName, pwd)
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	if resp.StatusCode != 200 {
		//log.Println("Warning: ", remoteURL, " not found!")
		return err
	}
	defer resp.Body.Close()
	out, err := os.Create(localFilePath)
	if err != nil {
		return err
	}
	_, err = io.Copy(out, resp.Body)
	out.Close()
	return err
}

// CSVJob ...
type CSVJob struct {
	TestName string
	JobURL   string
	BuildID  string
}

//DownloadJenkinsFiles ...
func DownloadJenkinsFiles(csvFile string) {
	props := properties.MustLoadFile("${HOME}/.jenkins_env.properties", properties.UTF8)
	//jenkinsServer := props.MustGetString("QA_JENKINS_SERVER")
	//jenkinsUser := props.MustGetString("QA_JENKINS_USER")
	//jenkinsUserPwd := props.MustGetString("QA_JENKINS_TOKEN")

	lines, err := ReadCsv(csvFile)
	if err != nil {
		log.Println(err)
		return
	}
	index := 0
	for _, line := range lines {
		data := CSVJob{
			TestName: line[0],
			JobURL:   line[1],
			BuildID:  line[2],
		}
		index++
		fmt.Println("\n" + strconv.Itoa(index) + "/" + strconv.Itoa(len(lines)) + ". " + data.TestName + " " + data.JobURL + " " + data.BuildID)

		// Start downloading
		req, _ := http.NewRequest("GET", data.JobURL, nil)
		JobName := path.Base(req.URL.Path)
		if JobName == data.BuildID {
			JobName = path.Base(req.URL.Path + "/..")
			data.JobURL = data.JobURL + ".."
		}

		// Update original URL in CB server if required to restore
		if strings.Contains(strings.ToLower(updateOrgURL), "yes") {
			qry := "update `server` set url='" + data.JobURL + "/" + JobName + "/' where `build`='" +
				cbbuild + "' and url like '%/" + JobName + "/' and  build_id=" + data.BuildID
			fmt.Println("CB update is in progress with qry= " + qry)
			if err := executeN1QLPostStmt(url, qry); err != nil {
				panic(err)
			}
			continue
		}

		JobDir := cbbuild + "/" + "jenkins_logs" + "/" + JobName + "/" + data.BuildID
		err := os.MkdirAll(JobDir, 0755)
		if err != nil {
			fmt.Println(err)
		}

		ConfigFile := JobDir + "/" + "config.xml"
		JobFile := JobDir + "/" + "jobinfo.json"
		ResultFile := JobDir + "/" + "testresult.json"
		LogFile := JobDir + "/" + "consoleText.txt"
		ArchiveZipFile := JobDir + "/" + "archive.zip"

		URLParts := strings.Split(data.JobURL, "/")
		jenkinsServer := strings.ToUpper(strings.Split(URLParts[2], ".")[0])

		if strings.Contains(strings.ToLower(jenkinsServer), s3bucket) {
			log.Println("CB Server run url is already pointing to S3.")
			continue
		}
		//fmt.Println("Jenkins Server: ", jenkinsServer)
		jenkinsUser := props.MustGetString(jenkinsServer + "_JENKINS_USER")
		jenkinsUserPwd := props.MustGetString(jenkinsServer + "_JENKINS_TOKEN")

		includedFiles := strings.Split(includes, ",")
		for i := 0; i < len(includedFiles); i++ {
			switch strings.ToLower(strings.TrimSpace(includedFiles[i])) {
			case "console":
				log.Println("...downloading console file")
				DownloadFileWithBasicAuth(LogFile, data.JobURL+data.BuildID+"/consoleText", jenkinsUser, jenkinsUserPwd)
				break
			case "config":
				log.Println("...downloading config file")
				DownloadFileWithBasicAuth(ConfigFile, data.JobURL+"/config.xml", jenkinsUser, jenkinsUserPwd)
				break
			case "parameters":
				log.Println("...downloading parameters file")
				DownloadFileWithBasicAuth(JobFile, data.JobURL+data.BuildID+"/api/json?pretty=true", jenkinsUser, jenkinsUserPwd)
				break
			case "testresult":
				log.Println("...downloading testresult file")
				DownloadFileWithBasicAuth(ResultFile, data.JobURL+data.BuildID+"/testReport/api/json?pretty=true", jenkinsUser, jenkinsUserPwd)
				break
			case "archive":
				log.Println("...downloading archive file")
				DownloadFileWithBasicAuth(ArchiveZipFile, data.JobURL+data.BuildID+"/artifact/*zip*/archive.zip", jenkinsUser, jenkinsUserPwd)
				break
			}
		}

		// Create index.html file
		indexFile := JobDir + "/" + "index.html"
		index, _ := os.Create(indexFile)
		defer index.Close()

		indexBuffer := bufio.NewWriter(index)
		fmt.Fprintf(indexBuffer, "<h1>CB Server build: %s</h1>\n<ul>", cbbuild)
		fmt.Fprintf(indexBuffer, "<h2>OS: %s</h2>\n<ul>", cbplatform)
		fmt.Fprintf(indexBuffer, "<h3>Test Suite: %s</h3>\n<ul>", data.TestName)
		// Save in AWS S3
		if strings.Contains(dest, "s3") {
			log.Println("Saving to S3 ...")
			//SaveInAwsS3(ConfigFile)
			for i := 0; i < len(includedFiles); i++ {
				switch strings.ToLower(strings.TrimSpace(includedFiles[i])) {
				case "console":
					if fileExists(LogFile) {
						SaveInAwsS3(LogFile)
						fmt.Fprintf(indexBuffer, "\n<li><a href=\"consoleText.txt\" target=\"_blank\">Jenkins job console log</a>")
					}
					break
				case "testresult":
					if fileExists(ResultFile) {
						SaveInAwsS3(ResultFile)
						fmt.Fprintf(indexBuffer, "\n<li><a href=\"testresult.json\" target=\"_blank\">Test result json</a>")
					}
					break
				case "config":
					if fileExists(ConfigFile) {
						SaveInAwsS3(ConfigFile)
						fmt.Fprintf(indexBuffer, "\n<li><a href=\"config.xml\" target=\"_blank\">Jenkins job config</a>")
					}
					break
				case "parameters":
					if fileExists(JobFile) {
						SaveInAwsS3(JobFile)
						fmt.Fprintf(indexBuffer, "\n<li><a href=\"jobinfo.json\" target=\"_blank\">Jenkins job parameters</a>")
					}
					break
				case "archive":
					if fileExists(ArchiveZipFile) {
						SaveInAwsS3(ArchiveZipFile)
						fmt.Fprintf(indexBuffer, "\n<li><a href=\"archive.zip\" target=\"_blank\">Jenkins artifacts archive zip</a>")
					}
					break
				}
			}
			fmt.Fprintf(indexBuffer, "\n</ul>")
			//SaveInAwsS3(ConfigFile, JobFile, ResultFile, LogFile)
			indexBuffer.Flush()

			if fileExists(indexFile) {
				SaveInAwsS3(indexFile)
				log.Println("Original URL: " + data.JobURL + data.BuildID + "/")
				log.Println("S3 URL: http://" + s3bucket + ".s3-website-us-west-2.amazonaws.com/" +
					cbbuild + "/" + "jenkins_logs" + "/" + JobName + "/" + data.BuildID + "/")
				// Update URL in CB server
				if strings.Contains(strings.ToLower(updateURL), "yes") && !strings.Contains(strings.ToLower(data.JobURL), s3bucket) {
					qry := "update `server` set url='http://" + s3bucket + ".s3-website-us-west-2.amazonaws.com/" +
						cbbuild + "/" + "jenkins_logs" + "/" + JobName + "/' where `build`='" +
						cbbuild + "' and url like '%/" + JobName + "/' and  build_id=" + data.BuildID
					fmt.Println("CB update in progress with qry= " + qry)
					if err := executeN1QLPostStmt(url, qry); err != nil {
						panic(err)
					}
				}
			}
		}

	}

}

// fileExists ...
func fileExists(filename string) bool {
	info, err := os.Stat(filename)
	if os.IsNotExist(err) {
		return false
	}
	return !info.IsDir()
}

// SaveInAwsS3 ...
func SaveInAwsS3(files ...string) {
	for i := 0; i < len(files); i++ {
		if overwrite == "no" {
			cmd1 := "aws s3 ls " + "s3://" + s3bucket + "/" + files[i]
			//fmt.Println(cmd1)
			cmd1Out := executeCommand(cmd1, "")
			//fmt.Println(cmd1, "--"+cmd1Out)
			fileParts := strings.Split(files[i], "/")
			fileName := fileParts[len(fileParts)-1]
			//fmt.Println("fileName=", fileName)
			if strings.Contains(cmd1Out, fileName) && overwrite == "no" {
				log.Println("Warning: Upload skip as AWS S3 already contains " + files[i] + " and overwrite=no")
			} else {
				SaveFileToS3(files[i])
			}
		} else {
			SaveFileToS3(files[i])
		}
	}
}

// SaveFileToS3 ...
func SaveFileToS3(objectName string) {
	cmd := "aws s3 cp " + objectName + " s3://" + s3bucket + "/" + objectName
	//fmt.Println("cmd=", cmd)
	outmesg := executeCommand(cmd, "")
	if outmesg != "" {
		log.Println(outmesg)
	}
	// read permission - only needed if bucket policy is not there
	//cmd = "aws s3api put-object-acl --bucket " + s3bucket + " --key " + objectName + " --acl public-read "
	//fmt.Println("cmd=", cmd)
	//outmesg = executeCommand(cmd, "")
	//if outmesg != "" {
	//	log.Println(outmesg)
	//}
}

// ReadCsv ... read csv file as double dimension array
func ReadCsv(filename string) ([][]string, error) {
	// Open CSV file
	f, err := os.Open(filename)
	if err != nil {
		return [][]string{}, err
	}
	defer f.Close()

	// Read File into a Variable
	lines, err := csv.NewReader(f).ReadAll()
	if err != nil {
		return [][]string{}, err
	}
	f.Close()
	return lines, nil
}

//SearchFile ...
func SearchFile(filename string, substring string) (string, error) {
	f, err := os.Open(filename)
	if err != nil {
		return "", err
	}
	defer f.Close()

	// Splits on newlines by default.
	scanner := bufio.NewScanner(f)

	line := 1
	linestring := ""
	// https://golang.org/pkg/bufio/#Scanner.Scan
	for scanner.Scan() {
		linestring = scanner.Text()
		if strings.Contains(linestring, substring) {
			f.Close()
			return linestring, nil
		}
		line++
	}

	if err := scanner.Err(); err != nil {
		log.Println(err)
		return "", err
	}
	f.Close()
	return linestring, err
}

//SearchFile2 ...
func SearchFile2(filename string, substring string) (string, error) {
	f, err := os.Open(filename)
	if err != nil {
		return "", err
	}
	defer f.Close()

	// Splits on newlines by default.
	scanner := bufio.NewReader(f)

	line := 1
	linestring := ""
	// https://golang.org/pkg/bufio/#Scanner.Scan
	for {
		linestring, err = scanner.ReadString('\n')
		if err != nil {
			f.Close()
			return "", err
		}
		if strings.Contains(linestring, substring) {
			f.Close()
			return linestring, nil
		}
		line++
	}
}

//SearchFileNextLines ...
func SearchFileNextLines(filename string, substring string) (string, error) {
	f, err := os.Open(filename)
	if err != nil {
		return "", err
	}
	defer f.Close()

	// Splits on newlines by default.
	scanner := bufio.NewScanner(f)

	line := 1
	linestring := ""
	// https://golang.org/pkg/bufio/#Scanner.Scan
	for scanner.Scan() {
		linestring = scanner.Text()
		if strings.Contains(linestring, substring) {
			scanner.Scan()
			linestring = scanner.Text()
			lines := linestring
			for linestring != "\n" && linestring != "" {
				lines += linestring + "\n"
				if scanner.Scan() {
					linestring = scanner.Text()
					log.Println(linestring)
				} else {
					break
				}
			}
			f.Close()
			return lines, nil
		}
		line++
	}

	if err := scanner.Err(); err != nil {
		log.Println(err)
		return "", err
	}
	return linestring, err
}

//SearchFileNextLines2 ...
func SearchFileNextLines2(filename string, substring string) (string, error) {
	f, err := os.Open(filename)
	if err != nil {
		return "", err
	}
	defer f.Close()

	// Splits on newlines by default.
	scanner := bufio.NewReader(f)

	line := 1
	linestring := ""
	// https://golang.org/pkg/bufio/#Scanner.Scan
	for {
		linestring, err = scanner.ReadString('\n')
		if err != nil {
			return "", nil
		}
		if strings.Contains(linestring, substring) {
			linestring, err = scanner.ReadString('\n')
			lines := ""
			for linestring != "\n" && linestring != "" && err != io.EOF {
				lines += linestring
				linestring, err = scanner.ReadString('\n')
				if err == nil {
					//log.Println(linestring)
					continue
				} else {
					break
				}
			}
			f.Close()
			return lines, nil
		}
		line++
	}

}
