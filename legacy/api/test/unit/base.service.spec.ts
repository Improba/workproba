import { BaseService } from '@lib-improba/base/base.service';

type TestEntity = { id: number };

describe('BaseService', () => {
  const mockRepository = {
    findOne: vi.fn(),
    findOneById: vi.fn(),
    findAll: vi.fn(),
    softDelete: vi.fn(),
  };

  let service: BaseService<TestEntity, typeof mockRepository>;

  beforeEach(() => {
    service = new BaseService(mockRepository);
    vi.clearAllMocks();
  });

  it('should find one entity', async () => {
    const entity = { id: 1 };
    mockRepository.findOne.mockResolvedValue(entity);

    const result = await service.findOne({ id: 1 });

    expect(result).toEqual(entity);
    expect(mockRepository.findOne).toHaveBeenCalledWith({ id: 1 });
  });

  it('should find one entity by id', async () => {
    const entity = { id: 2 };
    mockRepository.findOneById.mockResolvedValue(entity);

    const result = await service.findOneById(2);

    expect(result).toEqual(entity);
  });

  it('should find all entities', async () => {
    mockRepository.findAll.mockResolvedValue([{ id: 1 }]);

    const result = await service.findAll();

    expect(result).toEqual([{ id: 1 }]);
  });

  it('should soft delete entity', async () => {
    const entity = { id: 3 };
    mockRepository.softDelete.mockResolvedValue(entity);

    const result = await service.delete(3);

    expect(result).toEqual(entity);
  });
});
