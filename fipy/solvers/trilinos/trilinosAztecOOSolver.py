#!/usr/bin/env python

## -*-Pyth-*-
 # ###################################################################
 #  FiPy - Python-based finite volume PDE solver
 #
 #  FILE: "trilinosAztecOOSolver.py"
 #
 #  Author: Jonathan Guyer <guyer@nist.gov>
 #  Author: Daniel Wheeler <daniel.wheeler@nist.gov>
 #  Author: James Warren   <jwarren@nist.gov>
 #  Author: Maxsim Gibiansky <maxsim.gibiansky@nist.gov>
 #    mail: NIST
 #     www: http://www.ctcms.nist.gov/fipy/
 #
 # ========================================================================
 # This software was developed at the National Institute of Standards
 # and Technology by employees of the Federal Government in the course
 # of their official duties.  Pursuant to title 17 Section 105 of the
 # United States Code this software is not subject to copyright
 # protection and is in the public domain.  FiPy is an experimental
 # system.  NIST assumes no responsibility whatsoever for its use by
 # other parties, and makes no guarantees, expressed or implied, about
 # its quality, reliability, or any other characteristic.  We would
 # appreciate acknowledgement if the software is used.
 #
 # This software can be redistributed and/or modified freely
 # provided that any derivative works bear some notice that they are
 # derived from it, and any modified versions bear some notice that
 # they have been modified.
 # ========================================================================
 #
 # ###################################################################
 ##

__docformat__ = 'restructuredtext'

import os

from PyTrilinos import AztecOO

from fipy.solvers.trilinos.trilinosSolver import TrilinosSolver
from fipy.solvers.trilinos.preconditioners.jacobiPreconditioner import JacobiPreconditioner
from fipy.solvers import (NormalConvergence,
                          ParameterWarning, 
                          BreakdownWarning, 
                          LossOfPrecisionWarning,
                          MatrixIllConditionedWarning,
                          MaximumIterationWarning)

__all__ = ["TrilinosAztecOOSolver"]

class TrilinosAztecOOSolver(TrilinosSolver):

    """
    .. attention:: This class is abstract, always create on of its subclasses. It provides the code to call all solvers from the Trilinos AztecOO package.

    """
    
    AZ_r0 = AztecOO.AZ_r0
    AZ_rhs = AztecOO.AZ_rhs
    AZ_Anorm = AztecOO.AZ_Anorm
    AZ_noscaled = AztecOO.AZ_noscaled
    AZ_sol = AztecOO.AZ_sol
    
    @property
    def convergenceCheck(self):
        """Residual expression to compare to `tolerance`. 
        
        (see https://trilinos.org/oldsite/packages/aztecoo/AztecOOUserGuide.pdf)
        """
        return self._convergenceCheck
        
    @convergenceCheck.setter
    def convergenceCheck(self, value):
        self._convergenceCheck = value
    
    def __init__(self, tolerance=1e-10, iterations=1000, precon=JacobiPreconditioner()):
        """
        :Parameters:
          - `tolerance`: The required error tolerance.
          - `iterations`: The maximum number of iterative steps to perform.
          - `precon`: Preconditioner object to use.
        """
        if self.__class__ is TrilinosAztecOOSolver:
            raise NotImplementedError, "can't instantiate abstract base class"

        TrilinosSolver.__init__(self, tolerance=tolerance,
                                iterations=iterations, precon=None)
        self.preconditioner = precon
        self._convergenceCheck = None
        
    def _solve_(self, L, x, b):

        Solver = AztecOO.AztecOO(L, x, b)
        Solver.SetAztecOption(AztecOO.AZ_solver, self.solver)

##        Solver.SetAztecOption(AztecOO.AZ_kspace, 30)

        Solver.SetAztecOption(AztecOO.AZ_output, AztecOO.AZ_none)
        
        if self.convergenceCheck is not None:
            Solver.SetAztecOption(AztecOO.AZ_conv, self.convergenceCheck)

        if self.preconditioner is not None:
            self.preconditioner._applyToSolver(solver=Solver, matrix=L)
        else:
            Solver.SetAztecOption(AztecOO.AZ_precond, AztecOO.AZ_none)

        output = Solver.Iterate(self.iterations, self.tolerance)
        
        if self.preconditioner is not None:
            if hasattr(self.preconditioner, 'Prec'):
                del self.preconditioner.Prec
                
        status = Solver.GetAztecStatus()

        # normalize across solver packages
        self.status['iterations'] = status[AztecOO.AZ_its]
        self.status['residual'] = status[AztecOO.AZ_r]
        self.status['scaled residual'] = status[AztecOO.AZ_scaled_r]
        self.status['convergence residual'] = status[AztecOO.AZ_rec_r]
        self.status['solve time'] = status[AztecOO.AZ_solve_time]
        self.status['Aztec version'] = status[AztecOO.AZ_Aztec_version]
        self.status['code'] = self._warningDict[status[AztecOO.AZ_why]].__class__.__name__
        
        self._raiseWarning(status[AztecOO.AZ_why], 
                           status[AztecOO.AZ_its], 
                           status[AztecOO.AZ_scaled_r])

        if 'FIPY_VERBOSE_SOLVER' in os.environ:
            from fipy.tools.debug import PRINT
            PRINT('iterations: %d / %d' % (status[AztecOO.AZ_its], self.iterations))

            PRINT('failure', self._warningDict[status[AztecOO.AZ_why]].__class__.__name__)

            PRINT('AztecOO.AZ_r:',status[AztecOO.AZ_r])
            PRINT('AztecOO.AZ_scaled_r:',status[AztecOO.AZ_scaled_r])
            PRINT('AztecOO.AZ_rec_r:',status[AztecOO.AZ_rec_r])
            PRINT('AztecOO.AZ_solve_time:',status[AztecOO.AZ_solve_time])
            PRINT('AztecOO.AZ_Aztec_version:',status[AztecOO.AZ_Aztec_version])

        return output
        
    _warningDict = {AztecOO.AZ_normal : NormalConvergence,
                    AztecOO.AZ_param : ParameterWarning,
                    AztecOO.AZ_breakdown : BreakdownWarning,
                    AztecOO.AZ_loss : LossOfPrecisionWarning,
                    AztecOO.AZ_ill_cond : MatrixIllConditionedWarning,
                    AztecOO.AZ_maxits : MaximumIterationWarning}

    def _raiseWarning(self, info, iter, relres):
        if info != AztecOO.AZ_normal:
            # is stacklevel=5 always what's needed to get to the user's scope?
            import warnings
            warnings.warn(self._warningDict[info](self, iter, relres), stacklevel=5)



