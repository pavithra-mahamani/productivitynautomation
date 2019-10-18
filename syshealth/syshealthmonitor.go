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
	"net/http"
	"os"
	"os/exec"
	"sort"
	"strconv"
	"strings"
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

// PoolN1QLQryResult type
type PoolN1QLQryResult struct {
	Status  string
	Results []QEServerPool
}

// QEServerPool type
type QEServerPool struct {
	IPaddr  string
	Origin  string
	HostOS  string
	SpoolID string
	PoolID  []string
	State   string
}

// HostOSN1QLQryResult type
type HostOSN1QLQryResult struct {
	Status  string
	Results []HostOSCount
}

// HostOSCount type
type HostOSCount struct {
	HostOS string
	Count  int16
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

func main() {
	fmt.Println("\n*** Helper Tool ***")
	action := flag.String("action", "usage", usage())
	srcInput := flag.String("src", "cbserver", usage())
	destInput := flag.String("dest", "local", usage())
	overwriteInput := flag.String("overwrite", "no", usage())
	updateURLInput := flag.String("updateurl", "no", usage())
	cbplatformInput := flag.String("os", "centos", usage())
	s3bucketInput := flag.String("s3bucket", "cb-logs-qe", usage())
	urlInput := flag.String("cbqueryurl", "http://172.23.109.245:8093/query/service", usage())
	updateOrgURLInput := flag.String("updateorgurl", "no", usage())

	flag.Parse()
	dest = *destInput
	src = *srcInput
	overwrite = *overwriteInput
	updateURL = *updateURLInput
	cbplatform = *cbplatformInput
	s3bucket = *s3bucketInput
	url = *urlInput
	updateOrgURL = *updateOrgURLInput

	//fmt.Println("original dest=", dest, "--", *destInput)
	//time.Sleep(10 * time.Second)
	if *action == "runquery" {
		fmt.Println("Query Result: ", runquery(os.Args[len(os.Args)-1]))
	} else if *action == "getserverpoolhosts" {
		fmt.Println("Server Pool Hosts: ")
		GetServerPoolHosts()
	} else if *action == "getserverpoolinfo" {
		fmt.Println("GetServerPools info: ")
		GetServerPoolforIPs(os.Args[len(os.Args)-1])
	} else if *action == "healthchecks" {
		fmt.Println("HealthChecks: ")
		HealthChecks()
	} else if *action == "usage" {
		fmt.Println(usage())
	}
}

func usage() string {
	fileName, _ := os.Executable()
	return "Usage: " + fileName + " -h | --help \nEnter action value. \n" +
		"-action runquery 'select * from server where lower(`os`)=\"centos\" and `build`=\"6.5.0-4106\"' : to run a given query statement\n" +
		"-action getserverpoolhosts : to get the server pool host ips\n" +
		"-action getserverpoolinfo filename : to get the server pool info for given ips list file\n" +
		"-action healthchecks : to assess the VMs health\n"
}
func runquery(qry string) string {
	//url := "http://172.23.109.245:8093/query/service"
	fmt.Println("ACTION: runquery")
	fmt.Println("url=" + url)
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

// VMPoolsCSV ...
type VMPoolsCSV struct {
	PoolName string
	Count    int
}

// HealthChecks ...
func HealthChecks() {
	fmt.Println("action: healthcheck")
	poolsFile := "vmpools_centos.txt"
	iniFile := "cbqe_vms_per_pool_centos.ini"
	lines, err := ReadCsv(poolsFile)
	if err != nil {
		panic(err)
	}
	index := 0
	for _, line := range lines {
		data := VMPoolsCSV{
			PoolName: line[0],
		}
		index++
		fmt.Println("\n" + strconv.Itoa(index) + "/" + strconv.Itoa(len(lines)) + ". " + data.PoolName)
		//cmd := "ansible " + data.PoolName + " -i " + iniFile + " -u root -m ping |tee ping_output_" + data.PoolName + ".txt"
		cmd := "ansible " + data.PoolName + " -i " + iniFile + " -u root -m ping "
		fmt.Println("cmd= " + cmd)
		cmdOut := executeCommand("ansible "+data.PoolName+" -i "+iniFile+" -u root -m ping ", "")
		fmt.Println(cmdOut)
	}
}

//GetServerPoolHosts ...
func GetServerPoolHosts() {
	fmt.Println("action: getserverpoolhosts")

	url := "http://172.23.105.177:8093/query/service"
	qry := "select os as hostos, count(*) as count from `QE-server-pool` group by os order by os"
	//fmt.Println("query=" + qry)
	localFileName := "osresult.json"
	if err := executeN1QLStmt(localFileName, url, qry); err != nil {
		panic(err)
	}

	resultFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer resultFile.Close()

	byteValue, _ := ioutil.ReadAll(resultFile)

	var result HostOSN1QLQryResult

	err = json.Unmarshal(byteValue, &result)

	of, _ := os.Create("vms_os_count.txt")
	defer of.Close()
	ofw := bufio.NewWriter(of)

	if result.Status == "success" {
		fmt.Println("Platforms Count: ", len(result.Results))
		index := 1
		for i := 0; i < len(result.Results); i++ {
			if strings.TrimSpace(result.Results[i].HostOS) != "" {
				fmt.Println("\n---------------------------------------------------------")
				fmt.Printf("*** Platform#%d: %s\n", index, result.Results[i].HostOS)
				fmt.Println("---------------------------------------------------------")
				fmt.Fprintf(ofw, "%s: %d\n", result.Results[i].HostOS, result.Results[i].Count)
				GetServerPoolVMsPerPlatform(result.Results[i].HostOS)
				index++
			} else {
				fmt.Println("Empty platform")
			}
		}
		ofw.Flush()
	}
}

//GetServerPoolforIPs ...
func GetServerPoolforIPs(filename string) {

	url := "http://172.23.105.177:8093/query/service"

	//read from file
	f1, err1 := os.Open(filename)
	if err1 != nil {
		log.Println(err1)
	}
	defer f1.Close()

	// Splits on newlines by default.
	scanner := bufio.NewReader(f1)

	line := 0
	linestring := ""
	ipaddresses := ""

	// https://golang.org/pkg/bufio/#Scanner.Scan
	for {
		linestring, err1 = scanner.ReadString('\n')
		if err1 != nil {
			f1.Close()
			break
		}
		ipaddresses += "\"" + strings.TrimSpace(linestring) + "\","
		line++
	}

	/*for i := 0; i < len(IPs); i++ {
		ipaddresses += "\"" + IPs[i] + "\""
		if i < len(IPs)-1 {
			ipaddresses += ","
		}
	}*/
	index1 := strings.LastIndex(ipaddresses, ",")
	ipaddresses = ipaddresses[:index1]
	qry := "select ipaddr,origin,os as hostos,poolId as spoolId, poolId,state from `QE-server-pool` where ipaddr in [" + ipaddresses + "]"
	fmt.Println("query=" + qry)
	localFileName := "ipsresult.json"
	if err := executeN1QLStmt(localFileName, url, qry); err != nil {
		panic(err)
	}

	resultFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer resultFile.Close()

	byteValue, _ := ioutil.ReadAll(resultFile)

	var result PoolN1QLQryResult

	err = json.Unmarshal(byteValue, &result)
	//fmt.Println("Status=" + result.Status)
	//fmt.Println(err)
	f, err := os.Create("ips_pools_info.txt")
	defer f.Close()

	w := bufio.NewWriter(f)
	if result.Status == "success" {
		fmt.Println("Count: ", len(result.Results))
		for i := 0; i < len(result.Results); i++ {
			if result.Results[i].SpoolID != "" {
				//pools[result.Results[i].IPaddr] = pools[result.Results[i].SpoolID] + result.Results[i].IPaddr + "\n"
				fmt.Printf("%s,%s,%s,%s\n", result.Results[i].IPaddr, result.Results[i].HostOS, result.Results[i].SpoolID, result.Results[i].State)
				fmt.Fprintf(w, "%s,%s,%s,%s\n", result.Results[i].IPaddr, result.Results[i].HostOS, result.Results[i].SpoolID, result.Results[i].State)
			} else {
				poolids := ""
				for j := 0; j < len(result.Results[i].PoolID); j++ {
					//pools[result.Results[i].IPaddr] = pools[result.Results[i].PoolID[j]] + result.Results[i].IPaddr + "\n"
					poolids += result.Results[i].PoolID[j]
					if j < len(result.Results[i].PoolID)-1 {
						poolids += ";"
					}
				}
				fmt.Printf("%s,%s,%s,%s\n", result.Results[i].IPaddr, result.Results[i].HostOS, poolids, result.Results[i].State)
				fmt.Fprintf(w, "%s,%s,%s,%s\n", result.Results[i].IPaddr, result.Results[i].HostOS, poolids, result.Results[i].State)
			}
			w.Flush()
		}
		f.Close()

	} else {
		fmt.Println("Status: Failed")
	}
}

//GetServerPoolVMsPerPlatform ...
func GetServerPoolVMsPerPlatform(osplatform string) {

	url := "http://172.23.105.177:8093/query/service"
	//osplatform := "centos"
	qry := "select ipaddr,origin,os as hostos,poolId as spoolId, poolId,state from `QE-server-pool` where lower(`os`)='" + osplatform + "'"
	//fmt.Println("query=" + qry)
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

	var result PoolN1QLQryResult

	err = json.Unmarshal(byteValue, &result)
	//fmt.Println("Status=" + result.Status)
	//fmt.Println(err)
	f, err := os.Create("vmpools_" + osplatform + "_ips.ini")
	defer f.Close()

	w := bufio.NewWriter(f)
	if result.Status == "success" {
		fmt.Println("Count: ", len(result.Results))
		var pools map[string]string
		pools = make(map[string]string)
		var states map[string]string
		states = make(map[string]string)
		var poolswithstates map[string]string
		poolswithstates = make(map[string]string)
		var vms map[string]string
		vms = make(map[string]string)

		for i := 0; i < len(result.Results); i++ {
			//fmt.Println((i + 1), result.Results[i].Aname, result.Results[i].JURL, result.Results[i].URLbuild)
			//fmt.Print(result.Results[i].IPaddr, ", ", result.Results[i].HostOS, ", ", result.Results[i].State, ", [")
			//for j := 0; j < len(result.Results[i].PoolID); j++ {
			//	fmt.Print(result.Results[i].PoolID[j], ", ")
			//}
			//fmt.Println("]")
			//_, err = fmt.Fprintf(w, "%s,%s,%s\n", result.Results[i].IPaddr,
			//	result.Results[i].HostOS, result.Results[i].State)

			//pools level
			if result.Results[i].SpoolID != "" {
				//pools[result.Results[i].SpoolID+result.Results[i].HostOS] = pools[result.Results[i].SpoolID+result.Results[i].HostOS] + result.Results[i].IPaddr + "\n"
				pools[result.Results[i].SpoolID] = pools[result.Results[i].SpoolID] + result.Results[i].IPaddr + "\n"
				poolswithstates[result.Results[i].SpoolID+result.Results[i].State] = poolswithstates[result.Results[i].SpoolID+result.Results[i].State] + result.Results[i].IPaddr + "\n"
				vms[result.Results[i].IPaddr] = vms[result.Results[i].IPaddr] + result.Results[i].SpoolID + ","

				//fmt.Println("result.Results[i].SpoolID=", result.Results[i].SpoolID+", PoolID length=", len(result.Results[i].PoolID))
			} else {
				for j := 0; j < len(result.Results[i].PoolID); j++ {
					if !strings.Contains(result.Results[i].IPaddr, "[f") {
						pools[result.Results[i].PoolID[j]] = pools[result.Results[i].PoolID[j]] + result.Results[i].IPaddr + "\n"
						poolswithstates[result.Results[i].PoolID[j]+result.Results[i].State] = poolswithstates[result.Results[i].PoolID[j]+result.Results[i].State] + result.Results[i].IPaddr + "\n"
						vms[result.Results[i].IPaddr] = vms[result.Results[i].IPaddr] + result.Results[i].PoolID[j] + ","
					} else {
						pools[result.Results[i].PoolID[j]] = pools[result.Results[i].PoolID[j]] + "#" + result.Results[i].IPaddr + "\n"
						poolswithstates[result.Results[i].PoolID[j]+result.Results[i].State] = poolswithstates[result.Results[i].PoolID[j]+result.Results[i].State] + "#" + result.Results[i].IPaddr + "\n"
						vms[result.Results[i].IPaddr] = vms[result.Results[i].IPaddr] + result.Results[i].PoolID[j] + ","
					}
					//_, err = fmt.Fprintf(w, ",%s", result.Results[i].PoolID[j])
					//fmt.Println("result.Results[i].SpoolID=", result.Results[i].SpoolID+", PoolID length=", len(result.Results[i].PoolID))
				}

			}
			vms[result.Results[i].IPaddr] = vms[result.Results[i].IPaddr] + result.Results[i].State

			// states level
			if !strings.Contains(result.Results[i].IPaddr, "[f") {
				states[result.Results[i].State] = states[result.Results[i].State] + result.Results[i].IPaddr + "\n"
			} else {
				states[result.Results[i].State] = states[result.Results[i].State] + "#" + result.Results[i].IPaddr + "\n"
			}

		}
		//summary and generation of .ini - write to file
		fmt.Println("\nBy Pool")
		fmt.Println("---------")

		var keys []string
		for k := range pools {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		totalHosts := 0
		pf, _ := os.Create("vmpools_" + osplatform + "_counts.txt")
		defer pf.Close()
		pfw := bufio.NewWriter(pf)

		for _, k := range keys {
			nk := strings.ReplaceAll(k, " ", "")
			nk = strings.ReplaceAll(nk, "-", "")
			_, err = fmt.Fprintf(w, "\n[%s]\n%s", nk, pools[k])
			count := len(strings.Split(pools[k], "\n")) - 1
			totalHosts += count
			fmt.Printf("%s: %d\n", k, count)
			fmt.Fprintf(pfw, "%s: %d\n", k, count)
		}

		w.Flush()
		pfw.Flush()
		fmt.Println("\n Total: ", totalHosts)
		fmt.Println("\n NOTE: Check the created ini files at : ", f.Name(), " and ", pf.Name())

		fmt.Println("\nBy State")
		fmt.Println("----------")
		f1, err1 := os.Create("vmstates_" + osplatform + "_ips.ini")
		if err1 != nil {
			log.Println(err1)
		}
		defer f1.Close()
		w1 := bufio.NewWriter(f1)

		var skeys []string
		for k := range states {
			skeys = append(skeys, k)
		}
		sort.Strings(skeys)
		totalHosts = 0
		sf, _ := os.Create("vmstates_" + osplatform + "_counts.txt")
		defer sf.Close()
		sfw := bufio.NewWriter(sf)
		for _, k := range skeys {
			nk := strings.ReplaceAll(k, " ", "")
			nk = strings.ReplaceAll(nk, "-", "")
			_, err = fmt.Fprintf(w1, "\n[%s]\n%s", nk, states[k])
			count := len(strings.Split(states[k], "\n")) - 1
			totalHosts += count
			fmt.Printf("%s: %d\n", nk, count)
			fmt.Fprintf(sfw, "%s: %d\n", nk, count)
		}
		fmt.Println("\n Total: ", totalHosts)
		w1.Flush()
		sfw.Flush()
		fmt.Println("\n NOTE: Check the created ini files at : ", f1.Name(), " and ", sf.Name())

		fmt.Println("\nBy Pools with State")
		fmt.Println("---------------------")
		f2, err2 := os.Create("vmpoolswithstates_" + osplatform + "_ips.ini")
		if err2 != nil {
			log.Println(err2)
		}
		defer f2.Close()
		w2 := bufio.NewWriter(f2)

		var pskeys []string
		for k := range poolswithstates {
			pskeys = append(pskeys, k)
		}
		sort.Strings(pskeys)
		totalHosts = 0
		psf, _ := os.Create("vmpoolswithstates_" + osplatform + "_counts.txt")
		defer psf.Close()
		psfw := bufio.NewWriter(psf)
		for _, k := range pskeys {
			nk := strings.ReplaceAll(k, " ", "")
			nk = strings.ReplaceAll(nk, "-", "")
			_, err = fmt.Fprintf(w2, "\n[%s]\n%s", nk, poolswithstates[k])
			count := len(strings.Split(poolswithstates[k], "\n")) - 1
			totalHosts += count
			fmt.Printf("%s: %d\n", nk, count)
			fmt.Fprintf(psfw, "%s: %d\n", nk, count)
		}
		fmt.Println("\n Total: ", totalHosts)
		w2.Flush()
		psfw.Flush()

		fmt.Println("\nBy VMs")
		fmt.Println("---------------------")
		f3, err3 := os.Create("vms_list_" + osplatform + "_ips.ini")
		if err3 != nil {
			log.Println(err3)
		}
		defer f3.Close()
		w3 := bufio.NewWriter(f3)

		var vmkeys []string
		for k := range vms {
			vmkeys = append(vmkeys, k)
		}
		sort.Strings(vmkeys)
		totalHosts = 0
		vmsf, _ := os.Create("vms_list_" + osplatform + "_counts.txt")
		defer vmsf.Close()
		vmsfw := bufio.NewWriter(vmsf)
		for _, k := range vmkeys {
			_, err = fmt.Fprintf(w3, "\n%s: %s", k, vms[k])
			totalHosts++
			fmt.Printf("%s: %s\n", k, vms[k])
			fmt.Fprintf(vmsfw, "%s: %s\n", k, vms[k])
		}
		fmt.Println("\n Total: ", totalHosts)
		w3.Flush()
		vmsfw.Flush()

		fmt.Println("\n NOTE: Check the created ini files at : ", f3.Name(), " and ", vmsf.Name())
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
		return err
	} else {
		body, err := ioutil.ReadAll(resp.Body)
		log.Println(string(body))
		return err
	}

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

// fileExists ...
func fileExists(filename string) bool {
	info, err := os.Stat(filename)
	if os.IsNotExist(err) {
		return false
	}
	return !info.IsDir()
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
