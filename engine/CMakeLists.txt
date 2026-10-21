cmake_minimum_required(VERSION 3.24)

# The project version is the single source of engine_version in every payload.
project(laila_majnu_engine VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(LM_BUILD_TESTS "Build the Catch2 test suite" ON)
option(LM_SANITIZE "Build with AddressSanitizer and UndefinedBehaviorSanitizer" OFF)

include(cmake/warnings.cmake)

configure_file(src/version.hpp.in ${CMAKE_CURRENT_BINARY_DIR}/generated/lm/core/version.hpp @ONLY)

add_library(lm_core INTERFACE)
target_include_directories(lm_core INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${CMAKE_CURRENT_BINARY_DIR}/generated)
target_compile_features(lm_core INTERFACE cxx_std_20)

if(LM_SANITIZE)
  add_compile_options(-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()

if(LM_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()
