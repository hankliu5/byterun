import unittest
import numpy as np
import scipy.stats

from byterun.execfile import rsquare, estimate_coef


class TestN(unittest.TestCase):
    def setUp(self):
        self.x_arr = np.random.randint(1, 101, 100)
        self.y_arr = 5 * self.x_arr + np.random.random(len(self.x_arr))
        self.slope, self.intercept, r_value, _, _ = scipy.stats.linregress(self.x_arr, self.y_arr)
        self.r_square = r_value ** 2

    def test_custom_fitting_functions(self):
        custom_intercept, custom_slope = estimate_coef(self.x_arr, self.y_arr)
        custom_r_square = rsquare(custom_intercept, custom_slope, self.x_arr, self.y_arr)
        self.assertAlmostEqual(custom_intercept, self.intercept, delta=0.001)
        self.assertAlmostEqual(custom_slope, self.slope, delta=0.001)
        self.assertAlmostEqual(custom_r_square, self.r_square, delta=0.001)


class TestNlogN(unittest.TestCase):
    def setUp(self):
        self.x_arr = np.random.randint(1, 101, 100)
        self.y_arr = 5 * self.x_arr * np.log(self.x_arr) + np.random.random(len(self.x_arr))
        self.slope, self.intercept, r_value, _, _ = scipy.stats.linregress(self.x_arr, self.y_arr)
        self.r_square = r_value ** 2

    def test_custom_fitting_functions(self):
        custom_intercept, custom_slope = estimate_coef(self.x_arr, self.y_arr)
        custom_r_square = rsquare(custom_intercept, custom_slope, self.x_arr, self.y_arr)
        self.assertAlmostEqual(custom_intercept, self.intercept, delta=0.001)
        self.assertAlmostEqual(custom_slope, self.slope, delta=0.001)
        self.assertAlmostEqual(custom_r_square, self.r_square, delta=0.001)


class TestNSquared(unittest.TestCase):
    def setUp(self):
        self.x_arr = np.random.randint(1, 101, 100)
        self.y_arr = 5 * self.x_arr * self.x_arr + np.random.random(len(self.x_arr))
        self.slope, self.intercept, r_value, _, _ = scipy.stats.linregress(self.x_arr, self.y_arr)
        self.r_square = r_value ** 2

    def test_custom_fitting_functions(self):
        custom_intercept, custom_slope = estimate_coef(self.x_arr, self.y_arr)
        custom_r_square = rsquare(custom_intercept, custom_slope, self.x_arr, self.y_arr)
        self.assertAlmostEqual(custom_intercept, self.intercept, delta=0.001)
        self.assertAlmostEqual(custom_slope, self.slope, delta=0.001)
        self.assertAlmostEqual(custom_r_square, self.r_square, delta=0.001)
