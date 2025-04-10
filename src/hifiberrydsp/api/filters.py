import json
import math
import numpy as np
import cmath

class Filter:
    def __init__(self, **kwargs):
        self.params = kwargs

    def toJSON(self):
        return json.dumps(self.params)

    @staticmethod
    def normalize_biquad(b0, b1, b2, a0, a1, a2):
        """
        Normalize biquad coefficients by dividing all coefficients by a0
        to ensure a0 equals 1.0
        
        Args:
            b0, b1, b2: Numerator coefficients
            a0, a1, a2: Denominator coefficients
            
        Returns:
            Tuple of normalized coefficients (b0, b1, b2, 1.0, a1', a2')
        """
        # Return early if a0 is already 1 or close to it
        if abs(a0 - 1.0) < 1e-10:
            return (b0, b1, b2, a0, a1, a2)
            
        # Prevent division by zero
        if abs(a0) < 1e-10:
            raise ValueError("Cannot normalize biquad: a0 is too close to zero")
            
        # Normalize coefficients by dividing by a0
        return (b0/a0, b1/a0, b2/a0, 1.0, a1/a0, a2/a0)

    def biquadCoefficients(self):
        raise NotImplementedError("Subclasses must implement this method")

    def frequencyResponse(self, f, fs):
        """
        Calculate the complex frequency response of the filter at a specific frequency
        
        Args:
            f: Frequency in Hz
            fs: Sample rate in Hz
            
        Returns:
            Complex number representing the filter response at frequency f
        """
        # Get biquad coefficients for the filter
        try:
            coeffs = self.biquadCoefficients(fs)
            if not coeffs:
                return complex(1, 0)  # Neutral response if no coefficients
                
            # Extract coefficients: [b0, b1, b2, a0, a1, a2]
            b0, b1, b2, a0, a1, a2 = coeffs
            
            # Use normalized coefficients for calculation
            b0, b1, b2, a0, a1, a2 = Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)
            
            # Calculate z = e^(j*omega*T)
            omega = 2 * math.pi * f / fs
            z = cmath.rect(1, -omega)  # z^-1
            z2 = z * z  # z^-2
            
            # Calculate H(z) = (b0 + b1*z^-1 + b2*z^-2) / (1 + a1*z^-1 + a2*z^-2)
            # Since a0 = 1 after normalization, we can simplify the calculation
            numerator = b0 + b1 * z + b2 * z2
            denominator = 1 + a1 * z + a2 * z2
            
            return numerator / denominator
            
        except NotImplementedError:
            # Default to neutral response if not implemented
            return complex(1, 0)

    def frequencyResponseDb(self, f, fs):
        """
        Calculate the frequency response in decibels at a specific frequency
        
        Args:
            f: Frequency in Hz
            fs: Sample rate in Hz
            
        Returns:
            Amplitude response in decibels
        """
        response = self.frequencyResponse(f, fs)
        magnitude = abs(response)
        
        # Convert to decibels, handling edge case
        if magnitude > 0:
            return 20 * math.log10(magnitude)
        else:
            return -120  # Very small value in dB for zero magnitude
    
    @staticmethod
    def getFrequencyResponse(fs, filters, frequencies=None):
        """
        Calculate the combined frequency response of a chain of filters
        
        Args:
            fs: Sample rate in Hz
            filters: List of Filter objects
            frequencies: List of frequencies in Hz (optional)
                        If not provided, uses logarithmic scale from 20Hz to 20kHz
                        
        Returns:
            Dictionary with 'frequencies' and 'response' keys
        """
        # Generate default frequencies if not provided
        if frequencies is None:
            frequencies = Filter.logspace_frequencies(20, 20000, 8)
        
        # Initialize the response array with zeros (0 dB is neutral)
        response = np.zeros(len(frequencies))
        
        # Calculate the combined response at each frequency
        for filter_obj in filters:
            for i, freq in enumerate(frequencies):
                response[i] += filter_obj.frequencyResponseDb(freq, fs)
        
        return {
            'frequencies': frequencies,
            'response': response.tolist()
        }
    
    @staticmethod
    def logspace_frequencies(fmin, fmax, points_per_octave):
        """
        Generate logarithmically spaced frequencies
        
        Args:
            fmin: Minimum frequency in Hz
            fmax: Maximum frequency in Hz
            points_per_octave: Number of points per octave
            
        Returns:
            List of frequencies in Hz
        """
        # Calculate number of octaves
        num_octaves = math.log2(fmax / fmin)
        
        # Calculate total number of points
        num_points = int(points_per_octave * num_octaves) + 1
        
        # Generate log-spaced points
        frequencies = []
        for i in range(num_points):
            # Calculate frequency using logarithmic spacing
            exponent = i / points_per_octave
            freq = fmin * (2 ** exponent)
            
            # Make sure we don't exceed fmax
            if freq <= fmax:
                frequencies.append(freq)
            else:
                break
        
        # Make sure fmax is included
        if frequencies[-1] < fmax:
            frequencies.append(fmax)
            
        return frequencies

    @staticmethod
    def fromJSON(json_string):
        data = json.loads(json_string)
        filter_type = data.get("type")
        if filter_type == "PeakingEq":
            return PeakingEq(**data)
        elif filter_type == "LowPass":
            return LowPass(**data)
        elif filter_type == "HighPass":
            return HighPass(**data)
        elif filter_type == "LowShelf":
            return LowShelf(**data)
        elif filter_type == "HighShelf":
            return HighShelf(**data)
        elif filter_type == "Volume":
            return Volume(**data)
        else:
            raise ValueError(f"Unknown filter type: {filter_type}")

class PeakingEq(Filter):
    def __init__(self, f, db, q, **kwargs):
        super().__init__(f=f, db=db, q=q, **kwargs)
        self.f = f
        self.db = db
        self.q = q

    def biquadCoefficients(self, fs):
        omega = 2 * math.pi * self.f / fs
        alpha = math.sin(omega) / (2 * self.q)
        A = 10 ** (self.db / 40)
        
        b0 = 1 + alpha * A
        b1 = -2 * math.cos(omega)
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * math.cos(omega)
        a2 = 1 - alpha / A
        
        # Return normalized coefficients
        return Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)

class LowPass(Filter):
    def __init__(self, f, db, q, **kwargs):
        super().__init__(f=f, db=db, q=q, **kwargs)
        self.f = f
        self.db = db
        self.q = q

    def biquadCoefficients(self, fs):
        omega = 2 * math.pi * self.f / fs
        alpha = math.sin(omega) / (2 * self.q)
        
        b0 = (1 - math.cos(omega)) / 2
        b1 = 1 - math.cos(omega)
        b2 = (1 - math.cos(omega)) / 2
        a0 = 1 + alpha
        a1 = -2 * math.cos(omega)
        a2 = 1 - alpha
        
        # Return normalized coefficients
        return Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)

class HighPass(Filter):
    def __init__(self, f, db, q, **kwargs):
        super().__init__(f=f, db=db, q=q, **kwargs)
        self.f = f
        self.db = db
        self.q = q

    def biquadCoefficients(self, fs):
        omega = 2 * math.pi * self.f / fs
        alpha = math.sin(omega) / (2 * self.q)
        
        b0 = (1 + math.cos(omega)) / 2
        b1 = -(1 + math.cos(omega))
        b2 = (1 + math.cos(omega)) / 2
        a0 = 1 + alpha
        a1 = -2 * math.cos(omega)
        a2 = 1 - alpha
        
        # Return normalized coefficients
        return Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)

class LowShelf(Filter):
    def __init__(self, f, db, slope, gain, **kwargs):
        super().__init__(f=f, db=db, slope=slope, gain=gain, **kwargs)
        self.f = f
        self.db = db
        self.slope = slope
        self.gain = gain

    def biquadCoefficients(self, fs):
        A = 10 ** (self.gain / 40)
        omega = 2 * math.pi * self.f / fs
        alpha = math.sin(omega) / 2 * math.sqrt((A + 1/A) * (1/self.slope - 1) + 2)
        
        b0 = A * ((A + 1) - (A - 1) * math.cos(omega) + 2 * math.sqrt(A) * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * math.cos(omega))
        b2 = A * ((A + 1) - (A - 1) * math.cos(omega) - 2 * math.sqrt(A) * alpha)
        a0 = (A + 1) + (A - 1) * math.cos(omega) + 2 * math.sqrt(A) * alpha
        a1 = -2 * ((A - 1) + (A + 1) * math.cos(omega))
        a2 = (A + 1) + (A - 1) * math.cos(omega) - 2 * math.sqrt(A) * alpha
        
        # Return normalized coefficients
        return Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)

class HighShelf(Filter):
    def __init__(self, f, db, slope, gain, **kwargs):
        super().__init__(f=f, db=db, slope=slope, gain=gain, **kwargs)
        self.f = f
        self.db = db
        self.slope = slope
        self.gain = gain

    def biquadCoefficients(self, fs):
        A = 10 ** (self.gain / 40)
        omega = 2 * math.pi * self.f / fs
        alpha = math.sin(omega) / 2 * math.sqrt((A + 1/A) * (1/self.slope - 1) + 2)
        
        b0 = A * ((A + 1) + (A - 1) * math.cos(omega) + 2 * math.sqrt(A) * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * math.cos(omega))
        b2 = A * ((A + 1) + (A - 1) * math.cos(omega) - 2 * math.sqrt(A) * alpha)
        a0 = (A + 1) - (A - 1) * math.cos(omega) + 2 * math.sqrt(A) * alpha
        a1 = 2 * ((A - 1) - (A + 1) * math.cos(omega))
        a2 = (A + 1) - (A - 1) * math.cos(omega) - 2 * math.sqrt(A) * alpha
        
        # Return normalized coefficients
        return Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)

class Volume(Filter):
    def __init__(self, db, **kwargs):
        super().__init__(db=db, **kwargs)
        self.db = db

    def biquadCoefficients(self, fs):
        # A simple volume control can be implemented as a gain
        gain = 10 ** (self.db / 20)
        
        # For a simple gain, we only need b0
        b0 = gain
        b1 = 0
        b2 = 0
        a0 = 1
        a1 = 0
        a2 = 0
        
        # Since a0 is already 1, no need for normalization, but using the method for consistency
        return Filter.normalize_biquad(b0, b1, b2, a0, a1, a2)
