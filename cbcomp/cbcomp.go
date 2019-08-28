package main

import (
	"encoding/xml"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"os"
	"strings"
)

//Project type
type Project struct {
	XMLName xml.Name `xml:"project"`
	Name    string   `xml:"name,attr"`
	Remote  string   `xml:"remote,attr"`
	Path    string   `xml:"path,attr"`
	Groups  string   `xml:"groups,attr"`
}

// PRemote type
type PRemote struct {
	XMLName xml.Name `xml:"remote"`
	Name    string   `xml:"name,attr"`
	Fetch   string   `xml:"fetch,attr"`
	Review  string   `xml:"review,attr"`
}

// PDefault type
type PDefault struct {
	XMLName  xml.Name `xml:"default"`
	Remote   string   `xml:"remote,attr"`
	Revision string   `xml:"revision,attr"`
}

// Manifest type
type Manifest struct {
	XMLName  xml.Name   `xml:"manifest"`
	PRemote  []PRemote  `xml:"remote"`
	PDefault []PDefault `xml:"default"`
	Project  []Project  `xml:"project"`
}

func main() {
	xmlFileURL := "https://raw.githubusercontent.com/couchbase/manifest/master/couchbase-server/mad-hatter.xml"
	localFileName := "mad-hatter.xml"
	if err := DownloadFile(localFileName, xmlFileURL); err != nil {
		panic(err)
	}

	xmlFile, err := os.Open(localFileName)
	if err != nil {
		fmt.Println(err)
	}
	defer xmlFile.Close()

	byteValue, _ := ioutil.ReadAll(xmlFile)

	var manifest Manifest

	xml.Unmarshal(byteValue, &manifest)

	replacer := strings.NewReplacer("godeps/src/", "http://", "goproj/src/", "http://")

	for i := 0; i < len(manifest.Project); i++ {
		fmt.Println((i + 1), ",", manifest.Project[i].Name, ",",
			replacer.Replace(manifest.Project[i].Path), ", (",
			manifest.Project[i].Groups, ")")
	}
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
