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
	"sync"

	"github.com/magiconair/properties"
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
	Totaltime int64
}

const url = "http://172.23.109.245:8093/query/service"

var cbbuild string
var src string
var dest string
var overwrite string

func main() {
	fmt.Println("*** Helper Tool ***")
	action := flag.String("action", "usage", usage())
	srcInput := flag.String("src", "cbserver", usage())
	destInput := flag.String("dest", "local", usage())
	overwriteInput := flag.String("overwrite", "no", usage())
	flag.Parse()
	dest = *destInput
	src = *srcInput
	overwrite = *overwriteInput
	//fmt.Println("original dest=", dest, "--", *destInput)
	//time.Sleep(10 * time.Second)
	if *action == "lastaborted" {
		lastabortedjobs()
	} else if *action == "savejoblogs" {
		savejoblogs()
	} else if *action == "totalduration" {
		fmt.Println("Total duration: ", gettotalbuildcycleduration(os.Args[3]))
	} else if *action == "runquery" {
		fmt.Println("Query Result: ", runquery(os.Args[3]))
	} else if *action == "usage" {
		fmt.Println(usage())
	}
}

func usage() string {
	fileName, _ := os.Executable()
	return "Usage: " + fileName + " -h | --help \nEnter action value. \n" +
		"-action lastaborted 6.5.0-4106 6.5.0-4059 6.5.0-4000  : to get the aborted jobs common across last 3 builds\n" +
		"-action savejoblogs 6.5.0-4106  : to get the jenkins logs for a given build\n" +
		"-action totalduration 6.5.0-4106  : to get the total time duration for a build cyle\n" +
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

func gettotalbuildcycleduration(buildN string) string {
	fmt.Println("action: totalduration")

	//url := "http://172.23.109.245:8093/query/service"
	qry := "select sum(duration) as totaltime from server b where lower(b.os)=\"centos\" and b.`build`=\"" + buildN + "\""
	fmt.Println("query=" + qry)
	localFileName := "duration.json"
	if err := executeN1QLStmt(localFileName, url, qry); err != nil {
		panic(err)
	}

	resultFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer resultFile.Close()

	byteValue, _ := ioutil.ReadAll(resultFile)

	var result TotalCycleTimeQryResult

	err = json.Unmarshal(byteValue, &result)
	var ttime string
	if result.Status == "success" {
		fmt.Println("Total time in millis: ", result.Results[0].Totaltime)

		hours := math.Floor(float64(result.Results[0].Totaltime) / 1000 / 60 / 60)
		secs := result.Results[0].Totaltime % (1000 * 60 * 60)
		mins := math.Floor(float64(secs) / 60 / 1000)
		secs = result.Results[0].Totaltime * 1000 % 60
		fmt.Printf("%02d hrs : %02d mins :%02d secs", int64(hours), int64(mins), int64(secs))
		//ttime = string(hours) + ": " + string(mins) + ": " + string(secs)
	} else {
		fmt.Println("Status: Failed")
	}

	return ttime

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
		qry := "select b.name as aname,b.url as jurl,b.build_id urlbuild from server b where lower(b.os)=\"centos\" and b.`build`=\"" + build1 + "\""
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
		jobCsvFile = "all_jobs.csv"
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
	if len(os.Args) < 4 {
		fmt.Println("Enter the last 3 builds and first being the latest.")
		os.Exit(1)
	} else {
		build1 = os.Args[3]
		build2 = os.Args[4]
		build3 = os.Args[5]
	}

	//url := "http://172.23.109.245:8093/query/service"
	qry := "select b.name as aname,b.url as jurl,b.build_id urlbuild from server b where lower(b.os)=\"centos\" and b.result=\"ABORTED\" and b.`build`=\"" + build1 + "\" and b.name in (select raw a.name from server a where lower(a.os)=\"centos\" and a.result=\"ABORTED\" and a.`build`=\"" + build2 + "\" intersect select raw name from server where lower(os)=\"centos\" and result=\"ABORTED\" and `build`=\"" + build3 + "\" intersect select raw name from server where lower(os)=\"centos\" and result=\"ABORTED\" and `build`=\"" + build1 + "\")"
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
	f, err := os.Create("aborted_jobs.csv")
	defer f.Close()

	w := bufio.NewWriter(f)
	if result.Status == "success" {
		fmt.Println("Count: ", len(result.Results))
		for i := 0; i < len(result.Results); i++ {
			//fmt.Println((i + 1), result.Results[i].Aname, result.Results[i].JURL, result.Results[i].URLbuild)
			fmt.Print(strings.TrimSpace(result.Results[i].Aname), "\t", strings.TrimSpace(result.Results[i].JURL), "\t",
				result.Results[i].URLbuild)
			_, err = fmt.Fprintf(w, "%s,%s,%d\n", strings.TrimSpace(result.Results[i].Aname), strings.TrimSpace(result.Results[i].JURL),
				result.Results[i].URLbuild)
		}
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
	out, err := os.Create(localFilePath)
	if err != nil {
		return err
	}
	_, err = io.Copy(out, resp.Body)
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
		log.Println("Warning: ", remoteURL, " not found!")
		return err
	}
	defer resp.Body.Close()
	out, err := os.Create(localFilePath)
	if err != nil {
		return err
	}
	_, err = io.Copy(out, resp.Body)
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
		panic(err)
	}
	index := 0
	var wg sync.WaitGroup
	for _, line := range lines {
		data := CSVJob{
			TestName: line[0],
			JobURL:   line[1],
			BuildID:  line[2],
		}
		index++
		fmt.Println("\n" + strconv.Itoa(index) + "/" + strconv.Itoa(len(lines)) + ". " + data.TestName + " " + data.JobURL + " " + data.BuildID)
		wg.Add(1)
		go DownloadAndSaveToS3(&wg, props, data)
		if index%10 == 0 {
			log.Println("Waiting for the batch jobs to finish...")
			wg.Wait()
		}
	}
	log.Println("Waiting remaining jobs to finish...")
	wg.Wait()

}

// DownloadAndSaveToS3 ...
func DownloadAndSaveToS3(wg *sync.WaitGroup, props *properties.Properties, data CSVJob) {
	defer wg.Done()

	req, _ := http.NewRequest("GET", data.JobURL, nil)
	JobName := path.Base(req.URL.Path)
	if JobName == data.BuildID {
		JobName = path.Base(req.URL.Path + "/..")
		data.JobURL = data.JobURL + ".."
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
	//ArchiveZipFile := JobDir + "/" + "archive.zip"

	URLParts := strings.Split(data.JobURL, "/")
	jenkinsServer := strings.ToUpper(strings.Split(URLParts[2], ".")[0])
	//fmt.Println("Jenkins Server: ", jenkinsServer)
	jenkinsUser := props.MustGetString(jenkinsServer + "_JENKINS_USER")
	jenkinsUserPwd := props.MustGetString(jenkinsServer + "_JENKINS_TOKEN")

	DownloadFileWithBasicAuth(ConfigFile, data.JobURL+"/config.xml", jenkinsUser, jenkinsUserPwd)
	DownloadFileWithBasicAuth(JobFile, data.JobURL+data.BuildID+"/api/json?pretty=true", jenkinsUser, jenkinsUserPwd)
	DownloadFileWithBasicAuth(ResultFile, data.JobURL+data.BuildID+"/testReport/api/json?pretty=true", jenkinsUser, jenkinsUserPwd)
	DownloadFileWithBasicAuth(LogFile, data.JobURL+data.BuildID+"/consoleText", jenkinsUser, jenkinsUserPwd)
	//DownloadFileWithBasicAuth(ArchiveZipFile, data.JobURL+data.BuildID+"/artifact/*zip*/archive.zip", jenkinsUser, jenkinsUserPwd)

	// Save in AWS S3
	if strings.Contains(dest, "s3") {
		log.Println("Saving to S3 ...")
		//SaveInAwsS3(ConfigFile)
		if fileExists(ConfigFile) {
			SaveInAwsS3(ConfigFile)
		}
		if fileExists(JobFile) {
			SaveInAwsS3(JobFile)
		}
		if fileExists(ResultFile) {
			SaveInAwsS3(ResultFile)
		}
		if fileExists(LogFile) {
			SaveInAwsS3(LogFile)
		}
		//SaveInAwsS3(ConfigFile, JobFile, ResultFile, LogFile)
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
			cmd1 := "aws s3 ls " + "s3://cb-logs-qe/" + files[i]
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
	cmd := "aws s3 cp " + objectName + " s3://cb-logs-qe/" + objectName
	//fmt.Println("cmd=", cmd)
	outmesg := executeCommand(cmd, "")
	if outmesg != "" {
		log.Println(outmesg)
	}
	// read permission
	cmd = "aws s3api put-object-acl --bucket cb-logs-qe --key " + objectName + " --acl public-read "
	//fmt.Println("cmd=", cmd)
	outmesg = executeCommand(cmd, "")
	if outmesg != "" {
		log.Println(outmesg)
	}
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

	return lines, nil
}
