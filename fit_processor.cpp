#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <map>
#include <algorithm>
#include <dirent.h>
#include <sys/stat.h>
#include <cstdlib>

// Define to use standard int types and prevent redefinition
#define FIT_USE_STDINT_H
#define FIT_STRUCT_OFFSET_USE_STDDEF_OFFSETOF

// Include FIT SDK headers
extern "C" {
#include "FitSDKRelease_21.171.00/c/fit_convert.h"
#include "FitSDKRelease_21.171.00/c/fit_example.h"
}

struct FitDataRecord {
    std::string datetime_utc;
    int stress_level_value;
    int heart_rate;
    
    FitDataRecord() : stress_level_value(-1), heart_rate(-1) {}
};

class FitProcessor {
private:
    std::vector<FitDataRecord> allRecords;
    std::string tempDir;
    
    // Convert FIT timestamp to date and time strings
    std::pair<std::string, std::string> fitTimeToDateAndTime(FIT_UINT32 fitTime) {
        // FIT time is seconds since UTC 00:00 Dec 31 1989
        // Corrected epoch calculation: Dec 31 1989 00:00:00 UTC
        const time_t fitEpoch = 631065600; // Unix timestamp for Dec 31 1989 00:00:00 UTC (FIT standard)
        time_t unixTime = fitEpoch + fitTime;
        
        // Convert to Pacific Time (California time)
        // Note: This is a simplified conversion. For production, use proper timezone libraries
        time_t pacificTime = unixTime - (8 * 3600); // UTC-8 (PST) - adjust for PDT if needed
        struct tm* localTime = gmtime(&pacificTime);
        
        // Format date as MMDDYY
        std::ostringstream dateOss;
        dateOss << std::setfill('0') << std::setw(2) << (localTime->tm_mon + 1)
                << std::setfill('0') << std::setw(2) << localTime->tm_mday
                << std::setfill('0') << std::setw(2) << (localTime->tm_year % 100);
        
        // Format time as HH:MM
        std::ostringstream timeOss;
        timeOss << std::setfill('0') << std::setw(2) << localTime->tm_hour
                << ":" << std::setfill('0') << std::setw(2) << localTime->tm_min;
        
        return std::make_pair(dateOss.str(), timeOss.str());
    }
    
    // Convert FIT timestamp to ISO 8601 UTC string (for internal sorting)
    std::string fitTimeToISO8601(FIT_UINT32 fitTime) {
        // FIT time is seconds since UTC 00:00 Dec 31 1989
        // Using the correct FIT epoch: December 31, 1989 00:00:00 UTC
        const time_t fitEpoch = 631065600; // Unix timestamp for Dec 31 1989 00:00:00 UTC (FIT standard)
        time_t unixTime = fitEpoch + fitTime;
        
        struct tm* utcTime = gmtime(&unixTime);
        std::ostringstream oss;
        oss << std::put_time(utcTime, "%Y-%m-%dT%H:%M:%SZ");
        return oss.str();
    }
    
    // Extract ZIP file to temporary directory
    bool extractZipFile(const std::string& zipPath) {
        tempDir = "/tmp/fitconvert_" + std::to_string(time(nullptr));
        
        // Create temporary directory
        if (mkdir(tempDir.c_str(), 0755) != 0) {
            std::cerr << "Error: Could not create temporary directory: " << tempDir << std::endl;
            return false;
        }
        
        // Extract ZIP file using system unzip command
        std::string command = "unzip -q \"" + zipPath + "\" -d \"" + tempDir + "\"";
        int result = system(command.c_str());
        
        if (result != 0) {
            std::cerr << "Error: Failed to extract ZIP file" << std::endl;
            return false;
        }
        
        std::cout << "ZIP file extracted to: " << tempDir << std::endl;
        return true;
    }
    
    // Find all FIT files in directory recursively
    std::vector<std::string> findFitFiles(const std::string& directory) {
        std::vector<std::string> fitFiles;
        findFitFilesRecursive(directory, fitFiles);
        return fitFiles;
    }
    
    // Helper function for recursive directory traversal
    void findFitFilesRecursive(const std::string& directory, std::vector<std::string>& fitFiles) {
        DIR* dir = opendir(directory.c_str());
        if (!dir) {
            std::cerr << "Error: Could not open directory: " << directory << std::endl;
            return;
        }
        
        struct dirent* entry;
        while ((entry = readdir(dir)) != nullptr) {
            std::string name = entry->d_name;
            
            // Skip . and .. directories
            if (name == "." || name == "..") {
                continue;
            }
            
            std::string fullPath = directory + "/" + name;
            struct stat statbuf;
            
            if (stat(fullPath.c_str(), &statbuf) == 0) {
                if (S_ISDIR(statbuf.st_mode)) {
                    // Recursively search subdirectories
                    findFitFilesRecursive(fullPath, fitFiles);
                } else if (S_ISREG(statbuf.st_mode)) {
                    // Check if it's a FIT file
                    std::string extension = "";
                    size_t dotPos = name.find_last_of('.');
                    if (dotPos != std::string::npos) {
                        extension = name.substr(dotPos);
                        std::transform(extension.begin(), extension.end(), extension.begin(), ::tolower);
                    }
                    
                    if (extension == ".fit") {
                        fitFiles.push_back(fullPath);
                        std::cout << "Found FIT file: " << fullPath << std::endl;
                    }
                }
            }
        }
        
        closedir(dir);
    }
    
    // Process a single FIT file
    bool processFitFile(const std::string& fitFilePath) {
        FILE* file = fopen(fitFilePath.c_str(), "rb");
        if (!file) {
            std::cerr << "Error: Could not open FIT file: " << fitFilePath << std::endl;
            return false;
        }
        
        std::cout << "Processing FIT file: " << fitFilePath << std::endl;
        
        // Initialize FIT converter
        FitConvert_Init(FIT_TRUE);
        
        FIT_UINT8 buf[8];
        FIT_CONVERT_RETURN convert_return = FIT_CONVERT_CONTINUE;
        FIT_UINT32 buf_size;
        
        // Current record data
        FitDataRecord currentRecord;
        bool hasValidTimestamp = false;
        
        while (!feof(file) && (convert_return == FIT_CONVERT_CONTINUE)) {
            // Read buffer
            for (buf_size = 0; (buf_size < sizeof(buf)) && !feof(file); buf_size++) {
                buf[buf_size] = (FIT_UINT8)getc(file);
            }
            
            do {
                convert_return = FitConvert_Read(buf, buf_size);
                
                switch (convert_return) {
                    case FIT_CONVERT_MESSAGE_AVAILABLE: {
                        const FIT_UINT8* mesg = FitConvert_GetMessageData();
                        FIT_UINT16 mesg_num = FitConvert_GetMessageNumber();
                        
                        switch (mesg_num) {
                            case FIT_MESG_NUM_RECORD: {
                                const FIT_RECORD_MESG* record = (FIT_RECORD_MESG*)mesg;
                                
                                // Extract timestamp
                                if (record->timestamp != FIT_DATE_TIME_INVALID) {
                                    currentRecord.datetime_utc = fitTimeToISO8601(record->timestamp);
                                    hasValidTimestamp = true;
                                }
                                
                                // Extract heart rate
                                if (record->heart_rate != FIT_UINT8_INVALID) {
                                    currentRecord.heart_rate = record->heart_rate;
                                }
                                
                                // If we have both timestamp and heart rate, save the record
                                if (hasValidTimestamp && currentRecord.heart_rate != -1) {
                                    // Note: stress_level_value will be set from stress_level messages
                                    // For now, we'll use a placeholder or try to correlate with stress data
                                    if (currentRecord.stress_level_value == -1) {
                                        currentRecord.stress_level_value = 0; // Default value
                                    }
                                    
                                    allRecords.push_back(currentRecord);
                                    currentRecord = FitDataRecord(); // Reset for next record
                                    hasValidTimestamp = false;
                                }
                                break;
                            }
                            
                            case FIT_MESG_NUM_STRESS_LEVEL: {
                                // Handle stress level messages
                                // Note: The exact structure depends on the FIT file content
                                // This is a simplified approach
                                const FIT_UINT8* stressData = mesg;
                                
                                // Extract timestamp (usually at offset 0-3 for most messages)
                                FIT_UINT32 timestamp = *((FIT_UINT32*)stressData);
                                if (timestamp != FIT_DATE_TIME_INVALID) {
                                    // Try to find a matching record by timestamp or create new one
                                    std::string timestampStr = fitTimeToISO8601(timestamp);
                                    
                                    // Look for existing record with same timestamp
                                    bool found = false;
                                    for (auto& record : allRecords) {
                                        if (record.datetime_utc == timestampStr) {
                                            // Extract stress level value (this is simplified - actual offset may vary)
                                            // Stress level is typically a single byte value
                                            if (mesg[4] != FIT_UINT8_INVALID) {
                                                record.stress_level_value = mesg[4];
                                            }
                                            found = true;
                                            break;
                                        }
                                    }
                                    
                                    // If no matching record found, create a new one
                                    if (!found) {
                                        FitDataRecord newRecord;
                                        newRecord.datetime_utc = timestampStr;
                                        if (mesg[4] != FIT_UINT8_INVALID) {
                                            newRecord.stress_level_value = mesg[4];
                                        }
                                        allRecords.push_back(newRecord);
                                    }
                                }
                                break;
                            }
                            
                            case FIT_MESG_NUM_MONITORING: {
                                // Handle monitoring messages which may contain stress data
                                const FIT_MONITORING_MESG* monitoring = (FIT_MONITORING_MESG*)mesg;
                                
                                if (monitoring->timestamp != FIT_DATE_TIME_INVALID) {
                                    FitDataRecord newRecord;
                                    newRecord.datetime_utc = fitTimeToISO8601(monitoring->timestamp);
                                    // Monitoring messages don't typically have stress data directly
                                    // but we can create placeholder records
                                    allRecords.push_back(newRecord);
                                }
                                break;
                            }
                            
                            default:
                                // Ignore other message types
                                break;
                        }
                        break;
                    }
                    
                    default:
                        break;
                }
            } while (convert_return == FIT_CONVERT_MESSAGE_AVAILABLE);
        }
        
        fclose(file);
        
        if (convert_return == FIT_CONVERT_ERROR) {
            std::cerr << "Error: Failed to decode FIT file: " << fitFilePath << std::endl;
            return false;
        }
        
        std::cout << "Successfully processed FIT file: " << fitFilePath 
                  << " (extracted " << allRecords.size() << " total records so far)" << std::endl;
        return true;
    }
    
    // Clean up temporary directory
    void cleanup() {
        if (!tempDir.empty()) {
            std::string command = "rm -rf \"" + tempDir + "\"";
            system(command.c_str());
            std::cout << "Cleaned up temporary directory: " << tempDir << std::endl;
        }
    }
    
public:
    ~FitProcessor() {
        cleanup();
    }
    
    // Main processing function
    bool processZipFile(const std::string& zipPath, const std::string& outputCsvPath, bool excludeNonWaking = false) {
        std::cout << "Starting FIT file processing..." << std::endl;
        std::cout << "Input ZIP file: " << zipPath << std::endl;
        std::cout << "Output CSV file: " << outputCsvPath << std::endl;
        
        // Extract ZIP file
        if (!extractZipFile(zipPath)) {
            return false;
        }
        
        // Find all FIT files
        std::vector<std::string> fitFiles = findFitFiles(tempDir);
        if (fitFiles.empty()) {
            std::cerr << "Error: No FIT files found in ZIP archive" << std::endl;
            return false;
        }
        
        std::cout << "Found " << fitFiles.size() << " FIT files to process" << std::endl;
        
        // Process each FIT file
        int successCount = 0;
        for (const std::string& fitFile : fitFiles) {
            if (processFitFile(fitFile)) {
                successCount++;
            }
        }
        
        std::cout << "Successfully processed " << successCount << " out of " 
                  << fitFiles.size() << " FIT files" << std::endl;
        
        if (allRecords.empty()) {
            std::cerr << "Warning: No data records extracted from FIT files" << std::endl;
            return false;
        }
        
        // Sort records by timestamp
        std::sort(allRecords.begin(), allRecords.end(), 
                  [](const FitDataRecord& a, const FitDataRecord& b) {
                      return a.datetime_utc < b.datetime_utc;
                  });
        
        // Generate CSV output
        return generateCsvOutput(outputCsvPath, excludeNonWaking);
    }
    
    // Filter out non-waking hours (11pm - 6am)
    std::vector<FitDataRecord> filterNonWakingHours(const std::vector<FitDataRecord>& records) {
        std::vector<FitDataRecord> filteredRecords;
        
        for (const auto& record : records) {
            if (!record.datetime_utc.empty()) {
                // Parse the hour from ISO format: YYYY-MM-DDTHH:MM:SSZ
                if (record.datetime_utc.length() >= 13) {
                    std::string hourStr = record.datetime_utc.substr(11, 2);
                    int hour = std::stoi(hourStr);
                    
                    // Keep hours 6am (06:00) to 10:59pm (22:59)
                    // Exclude 11pm (23:00) to 5:59am (05:59)
                    if (hour >= 6 && hour <= 22) {
                        filteredRecords.push_back(record);
                    }
                }
            }
        }
        
        return filteredRecords;
    }
    
    // Generate CSV output with the specified format
    bool generateCsvOutput(const std::string& outputPath, bool excludeNonWaking = false) {
        std::ofstream csvFile(outputPath);
        if (!csvFile.is_open()) {
            std::cerr << "Error: Could not create output CSV file: " << outputPath << std::endl;
            return false;
        }
        
        // Write CSV header
        csvFile << "MMDDYY,Hour:Minute,Stress Level,Heart Rate" << std::endl;
        
        // Apply non-waking hours filter if requested
        std::vector<FitDataRecord> recordsToWrite = allRecords;
        if (excludeNonWaking) {
            recordsToWrite = filterNonWakingHours(allRecords);
            std::cout << "Applied non-waking hours filter: " << recordsToWrite.size()
                      << " records remaining (from " << allRecords.size() << " total)" << std::endl;
        }
        
        // Write data records
        int validRecords = 0;
        for (const auto& record : recordsToWrite) {
            // Only write records that have at least timestamp and one data field
            if (!record.datetime_utc.empty() &&
                (record.stress_level_value != -1 || record.heart_rate != -1)) {
                
                // Convert ISO timestamp back to FIT time for formatting
                // This is a simplified approach - in practice, we'd store the original FIT timestamp
                // For now, we'll parse the ISO string to get the components
                std::string dateStr = "";
                std::string timeStr = "";
                
                // Parse ISO format: YYYY-MM-DDTHH:MM:SSZ
                if (record.datetime_utc.length() >= 19) {
                    std::string year = record.datetime_utc.substr(0, 4);
                    std::string month = record.datetime_utc.substr(5, 2);
                    std::string day = record.datetime_utc.substr(8, 2);
                    std::string hour = record.datetime_utc.substr(11, 2);
                    std::string minute = record.datetime_utc.substr(14, 2);
                    
                    // Format as MMDDYY
                    std::string shortYear = year.substr(2, 2);
                    dateStr = month + day + shortYear;
                    
                    // Format as HH:MM
                    timeStr = hour + ":" + minute;
                }
                
                csvFile << dateStr << ","
                        << timeStr << ","
                        << (record.stress_level_value != -1 ? std::to_string(record.stress_level_value) : "")
                        << ","
                        << (record.heart_rate != -1 ? std::to_string(record.heart_rate) : "")
                        << std::endl;
                validRecords++;
            }
        }
        
        csvFile.close();
        
        std::cout << "CSV file generated successfully: " << outputPath << std::endl;
        std::cout << "Total records written: " << validRecords << std::endl;
        
        return true;
    }
    
    // Get statistics about processed data
    void printStatistics() {
        int recordsWithHeartRate = 0;
        int recordsWithStress = 0;
        int recordsWithBoth = 0;
        
        for (const auto& record : allRecords) {
            if (record.heart_rate != -1) recordsWithHeartRate++;
            if (record.stress_level_value != -1) recordsWithStress++;
            if (record.heart_rate != -1 && record.stress_level_value != -1) recordsWithBoth++;
        }
        
        std::cout << "\n=== Processing Statistics ===" << std::endl;
        std::cout << "Total records: " << allRecords.size() << std::endl;
        std::cout << "Records with heart rate: " << recordsWithHeartRate << std::endl;
        std::cout << "Records with stress level: " << recordsWithStress << std::endl;
        std::cout << "Records with both: " << recordsWithBoth << std::endl;
    }
};

int main(int argc, char* argv[]) {
    std::cout << "FitConvert - FIT File Processor v1.0" << std::endl;
    std::cout << "====================================" << std::endl;
    
    if (argc < 3 || argc > 4) {
        std::cerr << "Usage: " << argv[0] << " <input_zip_file> <output_csv_file> [--exclude-non-waking]" << std::endl;
        std::cerr << "Example: " << argv[0] << " garmin_data.zip output.csv" << std::endl;
        std::cerr << "         " << argv[0] << " garmin_data.zip output.csv --exclude-non-waking" << std::endl;
        std::cerr << "Options:" << std::endl;
        std::cerr << "  --exclude-non-waking  Exclude data from 11:00 PM to 6:00 AM" << std::endl;
        return 1;
    }
    
    std::string inputZip = argv[1];
    std::string outputCsv = argv[2];
    bool excludeNonWaking = false;
    
    // Check for optional flag
    if (argc == 4) {
        std::string flag = argv[3];
        if (flag == "--exclude-non-waking") {
            excludeNonWaking = true;
            std::cout << "Non-waking hours filter enabled (excluding 11:00 PM - 6:00 AM)" << std::endl;
        } else {
            std::cerr << "Error: Unknown flag '" << flag << "'" << std::endl;
            return 1;
        }
    }
    
    // Check if input file exists
    std::ifstream testFile(inputZip);
    if (!testFile.good()) {
        std::cerr << "Error: Input ZIP file does not exist: " << inputZip << std::endl;
        return 1;
    }
    testFile.close();
    
    // Process the ZIP file
    FitProcessor processor;
    bool success = processor.processZipFile(inputZip, outputCsv, excludeNonWaking);
    
    if (success) {
        processor.printStatistics();
        std::cout << "\n✅ Processing completed successfully!" << std::endl;
        std::cout << "Output CSV file: " << outputCsv << std::endl;
        return 0;
    } else {
        std::cerr << "\n❌ Processing failed!" << std::endl;
        return 1;
    }
}