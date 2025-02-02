"""
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree.

"""

import itertools
import unittest

import numpy as np

import torch

from distributed_shampoo.matrix_functions import _matrix_inverse_root_newton, _matrix_root_eigen


class EigenRootTest(unittest.TestCase):
    def _test_eigen_root(
        self,
        A,
        root,
        make_positive_semidefinite,
        inverse,
        epsilon,
        tolerance,
        eig_sols,
    ) -> None:
        X, L, Q = _matrix_root_eigen(
            A=A,
            root=root,
            epsilon=epsilon,
            make_positive_semidefinite=make_positive_semidefinite,
            inverse=inverse,
        )
        if inverse:
            root = -root
        abs_error = torch.dist(torch.linalg.matrix_power(X, root), A, p=torch.inf)
        A_norm = torch.linalg.norm(A, ord=torch.inf)
        rel_error = abs_error / torch.maximum(torch.tensor(1.0), A_norm)
        torch.testing.assert_close(L, eig_sols)
        self.assertLessEqual(rel_error, tolerance)

    def _test_eigen_root_multi_dim(
        self,
        A,
        dims,
        roots,
        make_positive_semidefinite,
        epsilons,
        tolerance,
        eig_sols,
    ) -> None:
        for n, root, epsilon in itertools.product(dims, roots, epsilons):
            with self.subTest(f"With dim = {n}, root = {root}, epsilon = {epsilon}"):
                self._test_eigen_root(
                    A(n),
                    root,
                    make_positive_semidefinite,
                    False,
                    epsilon,
                    tolerance,
                    eig_sols(n),
                )
                self._test_eigen_root(
                    A(n),
                    root,
                    make_positive_semidefinite,
                    True,
                    epsilon,
                    tolerance,
                    eig_sols(n),
                )

    def test_eigen_root_identity(self) -> None:
        tolerance = 1e-6
        dims = [10, 100]
        roots = [1, 2, 4, 8]
        epsilons = [0.0]
        make_positive_semidefinite = False

        def eig_sols(n):
            return torch.ones(n)

        def A(n):
            return torch.eye(n)

        self._test_eigen_root_multi_dim(
            A, dims, roots, make_positive_semidefinite, epsilons, tolerance, eig_sols
        )

    def test_eigen_root_tridiagonal_1(self) -> None:
        tolerance = 1e-4
        dims = [10, 100]
        roots = [1, 2, 4, 8]
        epsilons = [0.0]
        make_positive_semidefinite = False

        for alpha, beta in itertools.product(
            [0.001, 0.01, 0.1, 1.0, 10.0, 100.0], repeat=2
        ):
            if 2 * beta > alpha:
                continue

            with self.subTest(f"Test with alpha = {alpha}, beta = {beta}"):

                def eig_sols(n):
                    eigs = alpha * torch.ones(n) + 2 * beta * torch.tensor(
                        [np.cos(j * torch.pi / n) for j in range(n)], dtype=torch.float
                    )
                    eigs, _ = torch.sort(eigs)
                    return eigs

                def A(n):
                    diag = alpha * torch.ones(n)
                    diag[0] += beta
                    diag[n - 1] += beta
                    off_diag = beta * torch.ones(n - 1)
                    return (
                        torch.diag(diag)
                        + torch.diag(off_diag, diagonal=1)
                        + torch.diag(off_diag, diagonal=-1)
                    )

                self._test_eigen_root_multi_dim(
                    A,
                    dims,
                    roots,
                    make_positive_semidefinite,
                    epsilons,
                    tolerance,
                    eig_sols,
                )

    def test_eigen_root_tridiagonal_2(self) -> None:
        tolerance = 1e-4
        dims = [10, 100]
        roots = [1, 2, 4, 8]
        epsilons = [0.0]
        make_positive_semidefinite = False

        for alpha, beta in itertools.product(
            [0.001, 0.01, 0.1, 1.0, 10.0, 100.0], repeat=2
        ):
            if 2 * beta > alpha:
                continue

            with self.subTest(f"Test with alpha = {alpha}, beta = {beta}"):

                def eig_sols(n):
                    eigs = alpha * torch.ones(n) + 2 * beta * torch.tensor(
                        [
                            np.cos(2 * j * torch.pi / (2 * n + 1))
                            for j in range(1, n + 1)
                        ],
                        dtype=torch.float,
                    )
                    eigs, _ = torch.sort(eigs)
                    return eigs

                def A(n):
                    diag = alpha * torch.ones(n)
                    diag[0] -= beta
                    off_diag = beta * torch.ones(n - 1)
                    return (
                        torch.diag(diag)
                        + torch.diag(off_diag, diagonal=1)
                        + torch.diag(off_diag, diagonal=-1)
                    )

                self._test_eigen_root_multi_dim(
                    A,
                    dims,
                    roots,
                    make_positive_semidefinite,
                    epsilons,
                    tolerance,
                    eig_sols,
                )


class NewtonRootInverseTest(unittest.TestCase):
    def _test_newton_root_inverse(
        self, A, root, epsilon, max_iterations, A_tol, M_tol
    ) -> None:
        X, M, flag, iteration, M_error = _matrix_inverse_root_newton(
            A, root, epsilon, max_iterations, M_tol
        )
        abs_A_error = torch.dist(torch.linalg.matrix_power(X, -root), A, p=torch.inf)
        A_norm = torch.linalg.norm(A, ord=torch.inf)
        rel_A_error = abs_A_error / torch.maximum(torch.tensor(1.0), A_norm)
        self.assertLessEqual(M_error, M_tol)
        self.assertLessEqual(rel_A_error, A_tol)

    def _test_newton_root_inverse_multi_dim(
        self, A, dims, roots, epsilons, max_iterations, A_tol, M_tol
    ) -> None:

        for n, root, epsilon in itertools.product(dims, roots, epsilons):
            with self.subTest(f"With dim = {n}, root = {root}, epsilon = {epsilon}"):
                self._test_newton_root_inverse(
                    A(n), root, epsilon, max_iterations, A_tol, M_tol
                )

    def test_newton_root_inverse_identity(self) -> None:
        A_tol = 1e-6
        M_tol = 1e-6
        max_iterations = 1000
        dims = [10, 100]
        roots = [2, 4, 8]
        epsilons = [0.0]

        def A(n):
            return torch.eye(n)

        self._test_newton_root_inverse_multi_dim(
            A, dims, roots, epsilons, max_iterations, A_tol, M_tol
        )

    def test_newton_root_inverse_tridiagonal_1(self) -> None:
        A_tol = 1e-4
        M_tol = 1e-6
        max_iterations = 1000
        dims = [10, 100]
        roots = [2, 4, 8]
        epsilons = [0.0]

        for alpha, beta in itertools.product(
            [0.001, 0.01, 0.1, 1.0, 10.0, 100.0], repeat=2
        ):
            if 2 * beta > alpha:
                continue

            with self.subTest(f"Test with alpha = {alpha}, beta = {beta}"):

                def A(n):
                    diag = alpha * torch.ones(n)
                    diag[0] += beta
                    diag[n - 1] += beta
                    off_diag = beta * torch.ones(n - 1)
                    return (
                        torch.diag(diag)
                        + torch.diag(off_diag, diagonal=1)
                        + torch.diag(off_diag, diagonal=-1)
                    )

                self._test_newton_root_inverse_multi_dim(
                    A, dims, roots, epsilons, max_iterations, A_tol, M_tol
                )

    def test_newton_root_inverse_tridiagonal_2(self) -> None:
        A_tol = 1e-4
        M_tol = 1e-6
        max_iterations = 1000
        dims = [10, 100]
        roots = [2, 4, 8]
        epsilons = [0.0]

        for alpha, beta in itertools.product(
            [0.001, 0.01, 0.1, 1.0, 10.0, 100.0], repeat=2
        ):
            if 2 * beta > alpha:
                continue

            with self.subTest(f"Test with alpha = {alpha}, beta = {beta}"):

                def A(n):
                    diag = alpha * torch.ones(n)
                    diag[0] -= beta
                    off_diag = beta * torch.ones(n - 1)
                    return (
                        torch.diag(diag)
                        + torch.diag(off_diag, diagonal=1)
                        + torch.diag(off_diag, diagonal=-1)
                    )

                self._test_newton_root_inverse_multi_dim(
                    A, dims, roots, epsilons, max_iterations, A_tol, M_tol
                )


if __name__ == "__main__":
    unittest.main()
