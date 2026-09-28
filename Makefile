# FitConvert Makefile
# Compiles the FIT file processor using the Garmin FIT SDK

# Compiler settings
CXX = g++
CC = gcc
CXXFLAGS = -std=c++11 -Wall -Wextra -O2 -DFIT_USE_STDINT_H -DFIT_STRUCT_OFFSET_USE_STDDEF_OFFSETOF
CFLAGS = -Wall -Wextra -O2 -DFIT_USE_STDINT_H -DFIT_STRUCT_OFFSET_USE_STDDEF_OFFSETOF
INCLUDES = -I../FitSDKRelease_21.171.00/c
LIBS =

# FIT SDK source files
FIT_SDK_DIR = ../FitSDKRelease_21.171.00/c
FIT_SOURCES = $(FIT_SDK_DIR)/fit_convert.c \
              $(FIT_SDK_DIR)/fit_crc.c \
              $(FIT_SDK_DIR)/fit.c \
              $(FIT_SDK_DIR)/fit_example.c

# Target executable
TARGET = fit_processor
SOURCE = fit_processor.cpp

# Object files
FIT_OBJECTS = $(FIT_SOURCES:.c=.o)
CPP_OBJECTS = $(SOURCE:.cpp=.o)

# Default target
all: $(TARGET)

# Build the main executable
$(TARGET): $(CPP_OBJECTS) $(FIT_OBJECTS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LIBS)
	@echo "✅ FitConvert processor compiled successfully!"
	@echo "Usage: ./$(TARGET) <input.zip> <output.csv>"

# Compile C++ source
%.o: %.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

# Compile FIT SDK C sources
$(FIT_SDK_DIR)/%.o: $(FIT_SDK_DIR)/%.c
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# Clean build artifacts
clean:
	rm -f $(TARGET) $(CPP_OBJECTS) $(FIT_OBJECTS)
	@echo "🧹 Cleaned build artifacts"

# Install dependencies (macOS)
install-deps:
	@echo "📦 Installing dependencies..."
	@if command -v brew >/dev/null 2>&1; then \
		echo "Homebrew detected, no additional dependencies needed for basic build"; \
	else \
		echo "Please install Homebrew or ensure you have a C++ compiler installed"; \
	fi

# Test with sample data (if available)
test: $(TARGET)
	@echo "🧪 Testing FitConvert processor..."
	@if [ -f "test_data.zip" ]; then \
		./$(TARGET) test_data.zip test_output.csv; \
	else \
		echo "No test_data.zip found. Create a ZIP file with FIT files to test."; \
	fi

# Help target
help:
	@echo "FitConvert Makefile Help"
	@echo "======================="
	@echo "Available targets:"
	@echo "  all          - Build the FIT processor (default)"
	@echo "  clean        - Remove build artifacts"
	@echo "  install-deps - Install build dependencies"
	@echo "  test         - Test with sample data"
	@echo "  help         - Show this help message"
	@echo ""
	@echo "Usage after building:"
	@echo "  ./fit_processor input.zip output.csv"

.PHONY: all clean install-deps test help