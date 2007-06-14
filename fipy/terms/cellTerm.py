#!/usr/bin/env python

## -*-Pyth-*-
 # ###################################################################
 #  FiPy - Python-based finite volume PDE solver
 # 
 #  FILE: "cellTerm.py"
 #                                    created: 11/12/03 {11:00:54 AM} 
 #                                last update: 3/29/07 {10:40:50 AM} 
 #  Author: Jonathan Guyer <guyer@nist.gov>
 #  Author: Daniel Wheeler <daniel.wheeler@nist.gov>
 #  Author: James Warren   <jwarren@nist.gov>
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
 #  Description: 
 # 
 #  History
 # 
 #  modified   by  rev reason
 #  ---------- --- --- -----------
 #  2003-11-12 JEG 1.0 original
 # ###################################################################
 ##

__docformat__ = 'restructuredtext'

from fipy.tools import numerix

from fipy.terms.term import Term
from fipy.tools.inline import inline

from fipy.tools.sparseMatrix import _SparseMatrix

class CellTerm(Term):
    """
    .. attention:: This class is abstract. Always create one of its subclasses.
    """
    def __init__(self, coeff=1.):
        from fipy.variables.variable import Variable
        if not isinstance(coeff, Variable):
            from fipy.variables.constant import _Constant
            coeff = _Constant(value=coeff)

        from fipy.variables.cellVariable import CellVariable
        if not isinstance(coeff, CellVariable) \
        and coeff.getShape() != ():
            raise TypeError, "The coefficient must be a CellVariable or a scalar value."

        Term.__init__(self, coeff=coeff)
        self.coeffVectors = None
        self._var = None

    def _calcCoeffVectors(self, var):
        mesh = var.getMesh()
        coeff = self._getGeomCoeff(mesh)
        weight = self._getWeight(mesh)

        self.coeffVectors = {
            'diagonal': coeff * weight['diagonal'],
            'old value': coeff.getOld() * weight['old value'],
            'b vector': coeff * weight['b vector'],
            'new value': coeff * weight['new value']
        }

    def _getCoeffVectors(self, var):
        if self.coeffVectors is None or var != self._var:
            self._var = var
            self._calcCoeffVectors(var=var)
        return self.coeffVectors
        
    def _buildMatrixPy(self, L, oldArray, b, dt, coeffVectors):
        N = len(oldArray)

        b += numerix.array(oldArray) * numerix.array(coeffVectors['old value']) / dt
        b += numerix.ones([N]) * numerix.array(coeffVectors['b vector'])
        L.addAtDiagonal(numerix.ones([N]) * numerix.array(coeffVectors['new value']) / dt)
        L.addAtDiagonal(numerix.ones([N]) * numerix.array(coeffVectors['diagonal']))
        
##      L.addAtDiagonal(numerix.ones([N]) * numerix.array(coeffVectors['new value']) / dt)
##         L.addAtDiagonal(numerix.ones([N]) * numerix.array(coeffVectors['diagonal']))

    def _buildMatrixIn(self, L, oldArray, b, dt, coeffVectors):
        N = oldArray.getMesh().getNumberOfCells()
        updatePyArray = numerix.zeros((N),'d')

        inline._runInline("""
            b[i] += oldArray[i] * oldCoeff[i] / dt;
            b[i] += bCoeff[i];
            updatePyArray[i] += newCoeff[i] / dt;
            updatePyArray[i] += diagCoeff[i];
        """,b=b,
            oldArray=oldArray.getNumericValue(),
##            oldArray=numerix.array(oldArray),
            oldCoeff=numerix.array(coeffVectors['old value']),
            bCoeff=numerix.array(coeffVectors['b vector']),
            newCoeff=numerix.array(coeffVectors['new value']),
            diagCoeff=numerix.array(coeffVectors['diagonal']),
            updatePyArray=updatePyArray,
            ni=len(updatePyArray),
            dt=dt)

        L.addAtDiagonal(updatePyArray)
        
    def _buildMatrix(self, var, SparseMatrix, boundaryConditions=(), dt=1., equation=None):
        N = len(var)
        b = numerix.zeros((N),'d')
        L = SparseMatrix(size=N)
        
        # The sign of the matrix diagonal doesn't seem likely to change
        # after initialization, but who knows?
        if equation is not None:
            from fipy.tools.numerix import sign, add
            self._diagonalSign.setValue(sign(add.reduce(equation.matrix.takeDiagonal())))
        else:
            self._diagonalSign.setValue(1)
            
        coeffVectors = self._getCoeffVectors(var=var)

        inline._optionalInline(self._buildMatrixIn, self._buildMatrixPy, L, var.getOld(), b, dt, coeffVectors)
        
        return (L, b)
        
    def _test(self):
        """
        The following tests demonstrate how the `CellVariable` objects
        interact with other types of `Variable` objects.
        
            >>> from fipy.meshes.grid1D import Grid1D
            >>> from fipy.variables.cellVariable import CellVariable
            >>> from fipy.variables.faceVariable import FaceVariable
            >>> from fipy.variables.vectorCellVariable import VectorCellVariable
            >>> from fipy.variables.vectorFaceVariable import VectorFaceVariable
            >>> m = Grid1D(nx=2)
            >>> cv = CellVariable(mesh=m)
            >>> fv = FaceVariable(mesh=m)
            >>> vcv = VectorCellVariable(mesh=m)
            >>> vfv = VectorFaceVariable(mesh=m)
            >>> CellTerm(coeff=cv)
            CellTerm(coeff=CellVariable(value=array([ 0.,  0.]), mesh=UniformGrid1D(dx=1.0, nx=2)))
            >>> CellTerm(coeff=1)
            CellTerm(coeff=1)
            >>> CellTerm(coeff=fv)
            Traceback (most recent call last):
                ...
            TypeError: The coefficient must be a CellVariable or a scalar value.
            >>> CellTerm(coeff=vcv)
            Traceback (most recent call last):
                ...
            TypeError: The coefficient must be a CellVariable or a scalar value.
            >>> CellTerm(coeff=vfv)
            Traceback (most recent call last):
                ...
            TypeError: The coefficient must be a CellVariable or a scalar value.
            >>> CellTerm(coeff=(1,))
            Traceback (most recent call last):
                ...
            TypeError: The coefficient must be a CellVariable or a scalar value.

        """
        pass


def _test(): 
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
