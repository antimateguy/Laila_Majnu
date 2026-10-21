include(FetchContent)

# Pinned to the v3.16.1 release commit, not the tag, so a moved tag cannot change the build.
FetchContent_Declare(Catch2
  GIT_REPOSITORY https://github.com/catchorg/Catch2.git
  GIT_TAG        08092139210881f01a34e60c5f2fd6afa0ea4024  # v3.16.1
  GIT_SHALLOW    FALSE
  SYSTEM)
FetchContent_MakeAvailable(Catch2)

add_executable(lm_tests version_test.cpp)
target_link_libraries(lm_tests PRIVATE lm_core Catch2::Catch2WithMain)
lm_strict_warnings(lm_tests)

list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(Catch)
catch_discover_tests(lm_tests)
